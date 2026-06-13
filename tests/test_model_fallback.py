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


def test_runs_on_primary_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIMARY_MODEL", "gemini/gemini-3.5-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mf._model_cache.clear()
    expected = MagicMock(final_output="Gemini yanıtı")

    async def fake_run(agent, user_input, **kwargs):
        # Birincil model RunConfig ile geçilmeli.
        assert kwargs["run_config"].model is mf._get_litellm_model(
            "gemini/gemini-3.5-flash"
        )
        return expected

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "gemini"
    assert run.result is expected


def test_falls_back_to_openai_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIMARY_MODEL", "gemini/gemini-3.5-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("FALLBACK_MODEL", "openai")
    mf._model_cache.clear()

    calls: list[dict] = []
    openai_result = MagicMock(final_output="OpenAI yanıtı")

    async def fake_run(agent, user_input, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise _rate_limit_error()
        return openai_result

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "openai"
    assert run.result is openai_result
    assert len(calls) == 2
    # Fallback OpenAI default → run_config geçilmemeli.
    assert "run_config" not in calls[1]


def test_non_rate_limit_error_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIMARY_MODEL", "gemini/gemini-3.5-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mf._model_cache.clear()

    async def fake_run(agent, user_input, **kwargs):
        raise ValueError("beklenmeyen hata")

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        with pytest.raises(ValueError, match="beklenmeyen hata"):
            asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))


def test_primary_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIMARY_MODEL", "gemini/gemini-3.5-flash")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    mf._model_cache.clear()

    async def fake_run(agent, user_input, **kwargs):
        return MagicMock()

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))
