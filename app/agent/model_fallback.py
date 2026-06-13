"""Provider-flexible agent runner with automatic fallback.

The agent runs on a primary model (``PRIMARY_MODEL``, default Google Gemini's
free tier) through the OpenAI Agents SDK's LiteLLM integration. If the primary
model returns a quota or rate-limit error, the same agent (with the same tools
and conversation history) is retried on a fallback model (``FALLBACK_MODEL``,
default OpenAI). Use the sentinel ``openai`` to mean the agent's built-in
OpenAI model.

API keys are read from provider-specific environment variables, e.g.
``GEMINI_API_KEY`` for Gemini or ``ANTHROPIC_API_KEY`` for Claude.
"""

import os
from dataclasses import dataclass
from typing import Any

import openai
from agents import RunConfig, Runner


DEFAULT_PRIMARY_MODEL = "gemini/gemini-3.5-flash"
DEFAULT_FALLBACK_MODEL = "openai"
OPENAI_SENTINEL = "openai"

# LiteLLM sağlayıcı önekine karşılık gelen API anahtarı ortam değişkenleri.
PROVIDER_API_KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

_model_cache: dict[str, Any] = {}


@dataclass
class AgentRun:
    """Result of a fallback-aware agent run."""

    result: Any
    provider: str  # kullanılan sağlayıcı adı (ör. "gemini", "openai", "anthropic")


def _provider_of(model_name: str) -> str:
    """Return the LiteLLM provider prefix of a model name (e.g. 'gemini')."""
    return model_name.split("/", 1)[0] if "/" in model_name else model_name


def _is_openai_default(model_name: str) -> bool:
    """Whether the name means 'use the agent's built-in OpenAI model'."""
    return model_name.strip().lower() in {"", OPENAI_SENTINEL}


def _is_rate_limit(exc: Exception) -> bool:
    """Detect quota/rate-limit errors across OpenAI and LiteLLM providers."""
    if isinstance(exc, openai.RateLimitError):
        return True
    if "RateLimit" in type(exc).__name__:
        return True
    text = str(exc).lower()
    return "429" in text or "insufficient_quota" in text or "quota" in text


def _get_litellm_model(model_name: str) -> Any:
    """Build (and cache) a LiteLLM-backed model with the right API key."""
    if model_name in _model_cache:
        return _model_cache[model_name]

    from agents.extensions.models.litellm_model import LitellmModel

    provider = _provider_of(model_name)
    key_env = PROVIDER_API_KEY_ENV.get(provider, f"{provider.upper()}_API_KEY")
    api_key = os.getenv(key_env)
    if not api_key:
        raise RuntimeError(
            f"{key_env} tanımlı değil; model ({model_name}) kullanılamıyor."
        )

    model = LitellmModel(model=model_name, api_key=api_key)
    _model_cache[model_name] = model
    return model


async def _run_on(agent: Any, user_input: Any, model_name: str, **kwargs: Any) -> Any:
    """Run the agent on one model (OpenAI default or a LiteLLM model)."""
    if _is_openai_default(model_name):
        return await Runner.run(agent, user_input, **kwargs)
    model = _get_litellm_model(model_name)
    return await Runner.run(
        agent, user_input, run_config=RunConfig(model=model), **kwargs
    )


async def run_with_fallback(agent: Any, user_input: Any, **kwargs: Any) -> AgentRun:
    """Run ``agent`` on the primary model, falling back on quota/rate-limit errors."""
    primary = os.getenv("PRIMARY_MODEL", DEFAULT_PRIMARY_MODEL)
    try:
        result = await _run_on(agent, user_input, primary, **kwargs)
        return AgentRun(result=result, provider=_provider_of(primary))
    except Exception as exc:  # noqa: BLE001 - sadece kota/limit hatasında fallback
        if not _is_rate_limit(exc):
            raise

    fallback = os.getenv("FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)
    result = await _run_on(agent, user_input, fallback, **kwargs)
    return AgentRun(result=result, provider=_provider_of(fallback))
