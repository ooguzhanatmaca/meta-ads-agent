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


def test_retry_wait_parses_groq_tpm() -> None:
    exc = Exception(
        "GroqException - on tokens per minute (TPM): Limit 12000. "
        "Please try again in 7.815s."
    )
    assert mf._retry_wait_seconds(exc) == 7.815


def test_retry_wait_skips_daily_limit() -> None:
    exc = Exception("GenerateRequestsPerDayPerProjectPerModel ... retryDelay: 18s")
    assert mf._retry_wait_seconds(exc) is None


def test_retry_wait_caps_long_delays() -> None:
    assert mf._retry_wait_seconds(Exception("try again in 120s")) is None


def test_provider_glitch_detected() -> None:
    assert mf._is_provider_glitch(Exception("tool call validation failed: ..."))
    assert not mf._is_provider_glitch(Exception("some unrelated error"))


def test_access_blocked_detects_no_credit_and_auth() -> None:
    assert mf._is_access_blocked(Exception("Your credit balance is too low"))
    assert mf._is_access_blocked(Exception("please go to Plans & Billing"))
    assert mf._is_access_blocked(Exception("AuthenticationError 401"))
    assert not mf._is_access_blocked(Exception("some unrelated error"))


def test_transient_server_error_detected() -> None:
    assert mf._is_transient_server_error(Exception("GeminiException - 503 ... UNAVAILABLE"))
    assert mf._is_transient_server_error(Exception("model is overloaded, high demand"))
    assert not mf._is_transient_server_error(Exception("some unrelated error"))


def test_gemini_503_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    # Gemini 503 (geçici aşırı yük) -> agent çökmeden sıradaki modele geçmeli.
    monkeypatch.setenv("PRIMARY_MODEL", "gemini/gemini-2.5-flash")
    monkeypatch.setenv("FALLBACK_MODEL", "openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mf._model_cache.clear()

    ok = MagicMock(final_output="OpenAI yanıtı")

    async def fake_run(agent, user_input, **kwargs):
        if "run_config" in kwargs:  # gemini çağrısı: 503
            raise Exception(
                'litellm.ServiceUnavailableError: GeminiException - {"error": '
                '{"code": 503, "message": "high demand", "status": "UNAVAILABLE"}}'
            )
        return ok

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "openai"
    assert run.result is ok


def test_no_credit_balance_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    # Claude birincil ama bakiyesi yok -> agent çökmeden OpenAI'a düşmeli.
    monkeypatch.setenv("PRIMARY_MODEL", "anthropic/claude-sonnet-4-6")
    monkeypatch.setenv("FALLBACK_MODEL", "openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    mf._model_cache.clear()

    ok = MagicMock(final_output="OpenAI yanıtı")

    async def fake_run(agent, user_input, **kwargs):
        if "run_config" in kwargs:  # anthropic çağrısı: kredi yok
            raise Exception(
                "litellm.BadRequestError: AnthropicException - "
                "Your credit balance is too low to access the Anthropic API."
            )
        return ok

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "openai"
    assert run.result is ok


def test_provider_glitch_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIMARY_MODEL", "groq/llama-3.3-70b-versatile")
    monkeypatch.setenv("FALLBACK_MODEL", "openai")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    mf._model_cache.clear()

    ok = MagicMock(final_output="OpenAI yanıtı")

    async def fake_run(agent, user_input, **kwargs):
        if "run_config" in kwargs:  # groq → bozuk araç çağrısı
            raise Exception("GroqException - tool call validation failed")
        return ok

    with patch.object(mf.Runner, "run", side_effect=fake_run):
        run = asyncio.run(mf.run_with_fallback("AGENT", "merhaba"))

    assert run.provider == "openai"
    assert run.result is ok
