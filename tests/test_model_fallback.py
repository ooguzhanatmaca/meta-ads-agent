import asyncio
from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest

from app.agent import model_fallback as mf


def _rate_limit_error() -> openai.RateLimitError:
    response = httpx.Response(
        429, request=httpx.Request("POST", "https://api.openai.com")
    )
    return openai.RateLimitError("insufficient_quota", response=response, body=None)


def test_uses_openai_when_no_error() -> None:
    expected = MagicMock(final_output="OpenAI yanıtı")

    async def fake_run(agent, user_input, **kwargs):
        return expected

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "openai"
    assert run.result is expected


def test_falls_back_to_gemini_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FALLBACK_MODEL", "gemini/gemini-3.5-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mf._fallback_model = None  # reset cache

    calls: list[dict] = []
    fallback_result = MagicMock(final_output="Gemini yanıtı")

    async def fake_run(agent, user_input, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise _rate_limit_error()
        return fallback_result

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "gemini"
    assert run.result is fallback_result
    assert len(calls) == 2
    # İkinci çağrı fallback modelini RunConfig ile geçmeli.
    assert calls[1]["run_config"].model is mf._get_fallback_model()


def test_falls_back_to_claude_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FALLBACK_MODEL", "anthropic/claude-opus-4-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    mf._fallback_model = None  # reset cache

    async def fake_run(agent, user_input, **kwargs):
        if not getattr(fake_run, "called", False):
            fake_run.called = True
            raise _rate_limit_error()
        return MagicMock(final_output="Claude yanıtı")

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "anthropic"


def test_fallback_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FALLBACK_MODEL", "gemini/gemini-3.5-flash")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    mf._fallback_model = None  # reset cache

    async def fake_run(agent, user_input, **kwargs):
        raise _rate_limit_error()

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))
