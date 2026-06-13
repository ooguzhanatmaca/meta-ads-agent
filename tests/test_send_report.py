from unittest.mock import MagicMock, patch

import pytest

from app import send_report


def test_build_email_sets_headers_and_bodies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_USER", "sender@gmail.com")
    monkeypatch.setenv("REPORT_TO", "boss@example.com")

    message = send_report.build_email("RAPOR İÇERİĞİ <tablo>", "2026-06-13")

    assert message["From"] == "sender@gmail.com"
    assert message["To"] == "boss@example.com"
    assert "2026-06-13" in message["Subject"]
    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert "RAPOR İÇERİĞİ" in plain
    # HTML alternatifi monospace <pre> içermeli ve HTML kaçışı yapılmalı.
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "<pre" in html
    assert "&lt;tablo&gt;" in html


def test_build_email_defaults_recipient_to_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_USER", "sender@gmail.com")
    monkeypatch.delenv("REPORT_TO", raising=False)

    message = send_report.build_email("rapor", "2026-06-13")

    assert message["To"] == "sender@gmail.com"


def test_main_builds_and_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_USER", "sender@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.delenv("REPORT_TO", raising=False)

    sent = {}

    def fake_send(message):
        sent["message"] = message

    with patch.object(send_report, "load_dotenv", lambda: None), patch.object(
        send_report, "build_executive_summary", return_value="YÖNETİCİ ÖZETİ"
    ), patch.object(send_report, "send_email", side_effect=fake_send):
        code = send_report.main()

    assert code == 0
    plain = sent["message"].get_body(preferencelist=("plain",)).get_content()
    assert "YÖNETİCİ ÖZETİ" in plain


def test_main_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    with patch.object(send_report, "load_dotenv", lambda: None):
        assert send_report.main() == 1


def test_send_email_uses_starttls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_USER", "sender@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")

    server = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=server)
    cm.__exit__ = MagicMock(return_value=False)

    with patch.object(send_report.smtplib, "SMTP", return_value=cm) as smtp_cls:
        send_report.send_email(send_report.build_email("rapor", "2026-06-13"))

    smtp_cls.assert_called_once()
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("sender@gmail.com", "app-password")
    server.send_message.assert_called_once()
