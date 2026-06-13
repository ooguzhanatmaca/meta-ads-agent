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


def test_runs_on_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIMARY_MODEL", "gemini/gemini-2.0-flash")
    monkeypatch.setenv("FALLBACK_MODEL", "openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mf._model_cache.clear()
    expected = MagicMock(final_output="Gemini yanıtı")

    async def fake_run(agent, user_input, **kwargs):
        return expected

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "gemini"
    assert run.model == "gemini/gemini-2.0-flash"
    assert run.result is expected


def test_falls_through_chain_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIMARY_MODEL", "gemini/gemini-2.0-flash")
    monkeypatch.setenv("FALLBACK_MODEL", "gemini/gemini-2.5-flash,openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mf._model_cache.clear()

    calls: list[dict] = []
    final = MagicMock(final_output="OpenAI yanıtı")

    async def fake_run(agent, user_input, **kwargs):
        calls.append(kwargs)
        # İlk iki model (iki Gemini) kota hatası versin, OpenAI başarılı olsun.
        if "run_config" in kwargs:
            raise _rate_limit_error()
        return final

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "openai"
    assert run.result is final
    assert len(calls) == 3  # 2 gemini (rate-limited) + openai


def test_skips_model_with_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Birincil Claude (anahtar yok) atlanmalı, OpenAI'a düşmeli.
    monkeypatch.setenv("PRIMARY_MODEL", "anthropic/claude-opus-4-8")
    monkeypatch.setenv("FALLBACK_MODEL", "openai")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mf._model_cache.clear()

    async def fake_run(agent, user_input, **kwargs):
        return MagicMock(final_output="OpenAI yanıtı")

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "openai"


def test_all_exhausted_raises_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIMARY_MODEL", "gemini/gemini-2.0-flash")
    monkeypatch.setenv("FALLBACK_MODEL", "openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mf._model_cache.clear()

    async def fake_run(agent, user_input, **kwargs):
        raise _rate_limit_error()

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="kota/limit dolu"):
            asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))


def test_non_rate_limit_error_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIMARY_MODEL", "openai")
    monkeypatch.setenv("FALLBACK_MODEL", "")
    mf._model_cache.clear()

    async def fake_run(agent, user_input, **kwargs):
        raise ValueError("beklenmeyen hata")

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        with pytest.raises(ValueError, match="beklenmeyen hata"):
            asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))
