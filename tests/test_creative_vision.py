import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from app.meta import creative_vision as cv


def test_download_image_data_url(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock()
    response.content = b"\x89PNG\r\n"
    response.headers = {"Content-Type": "image/png"}
    response.raise_for_status = MagicMock()

    with patch.object(cv.requests, "get", return_value=response):
        data_url = cv._download_image_data_url("https://cdn.example.com/a.png")

    assert data_url.startswith("data:image/png;base64,")


def test_critique_image_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Sahte litellm enjekte et ki gerçek litellm .env'i yükleyip anahtarı geri koymasın.
    monkeypatch.setitem(sys.modules, "litellm", types.ModuleType("litellm"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        cv.critique_image("https://cdn.example.com/a.jpg")


def test_critique_image_calls_vision_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("VISION_MODEL", "gemini/gemini-2.0-flash")

    # Sahte litellm modülü enjekte et (gerçek API çağrısı olmasın).
    fake_litellm = types.ModuleType("litellm")
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        msg = MagicMock()
        msg.content = "Görsel geri bildirimi"
        choice = MagicMock()
        choice.message = msg
        result = MagicMock()
        result.choices = [choice]
        return result

    fake_litellm.completion = fake_completion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    with patch.object(
        cv, "_download_image_data_url", return_value="data:image/jpeg;base64,AAA"
    ):
        out = cv.critique_image("https://cdn.example.com/a.jpg")

    assert out == "Görsel geri bildirimi"
    assert captured["model"] == "gemini/gemini-2.0-flash"
    # İçerikte hem metin hem görsel bloğu olmalı.
    content = captured["messages"][0]["content"]
    assert any(b["type"] == "image_url" for b in content)
    assert any(b["type"] == "text" for b in content)
