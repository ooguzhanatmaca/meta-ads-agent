"""Provider-flexible agent runner with an automatic model fallback chain.

The agent runs on a primary model (``PRIMARY_MODEL``, default a generous
free-tier Gemini) through the OpenAI Agents SDK's LiteLLM integration. If a
model returns a quota/rate-limit error (or its API key is missing), the next
model in the chain (``FALLBACK_MODEL``, comma-separated) is tried with the same
agent, tools, and conversation history. Use the sentinel ``openai`` to mean the
agent's built-in OpenAI model.

API keys are read from provider-specific environment variables, e.g.
``GEMINI_API_KEY`` for Gemini or ``ANTHROPIC_API_KEY`` for Claude.
"""

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Any

import openai
from agents import RunConfig, Runner


MAX_RETRY_WAIT_SECONDS = 20.0


DEFAULT_PRIMARY_MODEL = "gemini/gemini-2.5-flash"
DEFAULT_FALLBACK_MODELS = "gemini/gemini-flash-latest,gemini/gemini-2.5-pro,openai"
OPENAI_SENTINEL = "openai"

PROVIDER_API_KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

_model_cache: dict[str, Any] = {}


class MissingApiKeyError(RuntimeError):
    """Raised when a model's provider API key is not configured."""


@dataclass
class AgentRun:
    """Result of a fallback-aware agent run."""

    result: Any
    provider: str  # kullanılan sağlayıcı adı (ör. "gemini", "openai")
    model: str  # kullanılan model adı


def _provider_of(model_name: str) -> str:
    return model_name.split("/", 1)[0] if "/" in model_name else model_name


def _is_openai_default(model_name: str) -> bool:
    return model_name.strip().lower() in {"", OPENAI_SENTINEL}


def _is_rate_limit(exc: Exception) -> bool:
    """Detect quota/rate-limit errors across OpenAI and LiteLLM providers."""
    if isinstance(exc, openai.RateLimitError):
        return True
    if "RateLimit" in type(exc).__name__:
        return True
    text = str(exc).lower()
    return "429" in text or "insufficient_quota" in text or "quota" in text


def _is_access_blocked(exc: Exception) -> bool:
    """Provider won't serve this model (no credits, billing, suspended/forbidden).

    These are not transient: the model simply can't run for this account, so we
    skip to the next model in the chain instead of crashing the whole agent.
    """
    text = str(exc).lower()
    if "credit balance" in text or "billing" in text or "purchase credits" in text:
        return True
    if "payment" in text and "required" in text:
        return True
    # 401/403: yetki/erişim engeli (anahtar geçersiz, izin yok) → bu modeli atla.
    return "401" in text or "403" in text or "permission_error" in text


def _is_provider_glitch(exc: Exception) -> bool:
    """Provider-side flakiness (ör. modelin bozuk araç çağrısı) — bu modeli atla."""
    text = str(exc).lower()
    return (
        "tool call validation" in text
        or "tool_use_failed" in text
        or "failed to call a function" in text
        or "did not match schema" in text
        or "no longer available" in text
        or "not_found" in text
        or "404" in text
    )


def _retry_wait_seconds(exc: Exception) -> float | None:
    """Seconds to wait before retrying the SAME model, or None to skip retrying.

    Only short per-minute/token-per-minute limits are worth waiting out; daily
    limits return None (move to the next model immediately).
    """
    text = str(exc)
    if "PerDay" in text or "per day" in text.lower():
        return None
    match = re.search(r"try again in\s*(\d+(?:\.\d+)?)\s*s", text, re.IGNORECASE)
    if match is None:
        match = re.search(r"retrydelay\W*(\d+(?:\.\d+)?)\s*s", text, re.IGNORECASE)
    if match:
        seconds = float(match.group(1))
        return seconds if seconds <= MAX_RETRY_WAIT_SECONDS else None
    return None


def _model_chain() -> list[str]:
    """Ordered, de-duplicated list of models to try (primary first)."""
    primary = os.getenv("PRIMARY_MODEL", DEFAULT_PRIMARY_MODEL).strip()
    fallbacks = os.getenv("FALLBACK_MODEL", DEFAULT_FALLBACK_MODELS)
    candidates = [primary] + [m.strip() for m in fallbacks.split(",")]
    chain: list[str] = []
    for model in candidates:
        if model and model not in chain:
            chain.append(model)
    return chain


def _get_litellm_model(model_name: str) -> Any:
    """Build (and cache) a LiteLLM-backed model with the right API key."""
    if model_name in _model_cache:
        return _model_cache[model_name]

    from agents.extensions.models.litellm_model import LitellmModel

    provider = _provider_of(model_name)
    key_env = PROVIDER_API_KEY_ENV.get(provider, f"{provider.upper()}_API_KEY")
    api_key = os.getenv(key_env)
    if not api_key:
        raise MissingApiKeyError(
            f"{key_env} tanımlı değil; model ({model_name}) atlanıyor."
        )

    model = LitellmModel(model=model_name, api_key=api_key)
    _model_cache[model_name] = model
    return model


async def _run_on(agent: Any, user_input: Any, model_name: str, **kwargs: Any) -> Any:
    if _is_openai_default(model_name):
        return await Runner.run(agent, user_input, **kwargs)
    model = _get_litellm_model(model_name)
    return await Runner.run(
        agent, user_input, run_config=RunConfig(model=model), **kwargs
    )


async def run_with_fallback(agent: Any, user_input: Any, **kwargs: Any) -> AgentRun:
    """Run ``agent`` through the model chain until one succeeds."""
    chain = _model_chain()
    for model_name in chain:
        retried = False
        while True:
            try:
                result = await _run_on(agent, user_input, model_name, **kwargs)
                return AgentRun(
                    result=result,
                    provider=_provider_of(model_name),
                    model=model_name,
                )
            except MissingApiKeyError:
                break  # anahtar yoksa bu modeli atla
            except Exception as exc:  # noqa: BLE001
                if _is_rate_limit(exc):
                    # Kısa dakikalık/token limitiyse bir kez bekleyip aynı modeli dene.
                    wait = _retry_wait_seconds(exc) if not retried else None
                    if wait is not None:
                        retried = True
                        await asyncio.sleep(wait + 1)
                        continue
                    break  # günlük/uzun limit → sıradaki modele geç
                if _is_provider_glitch(exc):
                    break  # modelin geçici hatası → sıradaki modele geç
                if _is_access_blocked(exc):
                    break  # kredi/bakiye/yetki engeli → sıradaki modele geç
                raise  # gerçek hata → yükselt

    raise RuntimeError(
        "Tüm modeller şu an kota/limit dolu veya yapılandırılmamış. "
        "Birkaç dakika bekleyip tekrar dene ya da .env içindeki PRIMARY_MODEL'i değiştir."
    )
