"""Build the executive summary and e-mail it (e.g. as a daily report).

Configuration (in .env):
    SMTP_USER       Gmail adresin (gönderen)
    SMTP_PASSWORD   Gmail "Uygulama Şifresi" (16 haneli, normal şifre değil)
    REPORT_TO       Alıcı e-posta (boşsa SMTP_USER'a gönderilir)
    SMTP_HOST       Varsayılan: smtp.gmail.com
    SMTP_PORT       Varsayılan: 587 (STARTTLS)

Çalıştırma:
    .venv/bin/python -m app.send_report
"""

import os
import smtplib
import sys
from datetime import date
from email.message import EmailMessage

from dotenv import load_dotenv

from app.meta.anomaly_report import collect_alerts, format_alerts
from app.meta.client import MetaAPIError
from app.meta.executive_summary import build_executive_summary


DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587


def build_email(body: str, subject: str) -> EmailMessage:
    """Compose the report e-mail (plain text + monospace HTML)."""
    sender = os.environ["SMTP_USER"]
    recipient = os.getenv("REPORT_TO") or sender

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)
    report = body
    # Sabit genişlikli tablolar e-postada düzgün görünsün diye <pre>.
    escaped = report.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    message.add_alternative(
        f"<pre style=\"font-family:monospace;font-size:13px\">{escaped}</pre>",
        subtype="html",
    )
    return message


def send_email(message: EmailMessage) -> None:
    """Send the e-mail via SMTP with STARTTLS."""
    host = os.getenv("SMTP_HOST", DEFAULT_SMTP_HOST)
    port = int(os.getenv("SMTP_PORT", DEFAULT_SMTP_PORT))
    password = os.environ["SMTP_PASSWORD"]

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(os.environ["SMTP_USER"], password)
        server.send_message(message)


def main() -> int:
    load_dotenv()

    if not os.getenv("SMTP_USER") or not os.getenv("SMTP_PASSWORD"):
        print("SMTP_USER ve SMTP_PASSWORD .env içinde tanımlı olmalı.")
        return 1

    try:
        alerts = collect_alerts()
        summary = build_executive_summary()
    except MetaAPIError as error:
        print(f"Rapor oluşturulamadı: {error}")
        return 1

    today = date.today().isoformat()
    # E-posta uyarılarla başlar, ardından tam yönetici özeti gelir.
    body = f"{format_alerts(alerts)}\n\n{'=' * 60}\n\n{summary}"
    if alerts:
        subject = f"⚠️ Meta Ads: {len(alerts)} uyarı - {today}"
    else:
        subject = f"✅ Meta Ads Günlük Rapor (sorun yok) - {today}"

    try:
        send_email(build_email(body, subject))
    except (smtplib.SMTPException, OSError) as error:
        print(f"E-posta gönderilemedi: {error}")
        return 1

    recipient = os.getenv("REPORT_TO") or os.environ["SMTP_USER"]
    print(f"Rapor gönderildi → {recipient}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
