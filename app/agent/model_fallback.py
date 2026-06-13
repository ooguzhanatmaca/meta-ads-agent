"""OpenAI-first agent runner with an automatic LiteLLM fallback.

The agent normally runs on the configured OpenAI model. When OpenAI returns a
quota or rate-limit error, the same agent (with the same tools) is retried on a
fallback model through the OpenAI Agents SDK's LiteLLM integration.

The fallback model is configured with ``FALLBACK_MODEL`` in LiteLLM format and
defaults to Google Gemini's free tier (``gemini/gemini-2.0-flash``). The matching
API key is read from the provider-specific environment variable, e.g.
``GEMINI_API_KEY`` for Gemini or ``ANTHROPIC_API_KEY`` for Claude.
"""

import os
from dataclasses import dataclass
from typing import Any

import openai
from agents import RunConfig, Runner


DEFAULT_FALLBACK_MODEL = "gemini/gemini-3.5-flash"

# LiteLLM sağlayıcı önekine karşılık gelen API anahtarı ortam değişkenleri.
PROVIDER_API_KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

_fallback_model: Any = None


@dataclass
class AgentRun:
    """Result of a fallback-aware agent run."""

    result: Any
    provider: str  # "openai" veya fallback sağlayıcı adı (ör. "gemini")


def _provider_of(model_name: str) -> str:
    """Return the LiteLLM provider prefix of a model name (e.g. 'gemini')."""
    return model_name.split("/", 1)[0] if "/" in model_name else model_name


def _get_fallback_model() -> Any:
    """Build (and cache) the LiteLLM-backed fallback model."""
    global _fallback_model
    if _fallback_model is not None:
        return _fallback_model

    from agents.extensions.models.litellm_model import LitellmModel

    model_name = os.getenv("FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)
    provider = _provider_of(model_name)
    key_env = PROVIDER_API_KEY_ENV.get(provider, f"{provider.upper()}_API_KEY")
    api_key = os.getenv(key_env)
    if not api_key:
        raise RuntimeError(
            f"{key_env} tanımlı değil; fallback modeli ({model_name}) kullanılamıyor."
        )

    _fallback_model = LitellmModel(model=model_name, api_key=api_key)
    return _fallback_model


async def run_with_fallback(agent: Any, user_input: Any, **kwargs: Any) -> AgentRun:
    """Run ``agent`` on OpenAI, falling back to LiteLLM on quota/rate-limit errors."""
    try:
        result = await Runner.run(agent, user_input, **kwargs)
        return AgentRun(result=result, provider="openai")
    except openai.RateLimitError:
        fallback_model = _get_fallback_model()
        result = await Runner.run(
            agent, user_input, run_config=RunConfig(model=fallback_model), **kwargs
        )
        model_name = os.getenv("FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)
        return AgentRun(result=result, provider=_provider_of(model_name))
