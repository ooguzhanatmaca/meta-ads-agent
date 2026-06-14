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

from app.meta.account_summary import calculate_summary
from app.meta.anomaly_report import collect_alerts, format_alerts
from app.meta.autopilot import build_autopilot_section
from app.meta.client import (
    MetaAPIError,
    get_account_insights,
    get_performance_report,
)
from app.meta.executive_summary import build_executive_summary
from app.meta.performance_report import calculate_report_rows
from app.meta import history


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


def save_daily_snapshots() -> None:
    """Persist today's metrics so the agent builds longitudinal history over time.

    Best-effort: any failure here must not block the e-mail report.
    """
    try:
        from app.meta.client import MetaClient

        account_id = MetaClient.from_env().ad_account_id
    except Exception:  # noqa: BLE001
        account_id = "-"

    conn = history.connect()
    try:
        summary = calculate_summary(get_account_insights("last_7d"))
        reach = summary.get("reach") or 0
        summary["frequency"] = summary["impressions"] / reach if reach else 0.0
        history.save_snapshot(
            conn,
            "account",
            [{"id": "account", "name": "Hesap", "status": "-", **summary}],
            account_id=account_id,
        )
        for level in ("campaign", "adset", "ad"):
            rows = calculate_report_rows(get_performance_report(level, "last_7d"))
            history.save_snapshot(conn, level, rows, account_id=account_id)
    except MetaAPIError as error:
        print(f"Snapshot kaydedilemedi (rapor yine de gönderilecek): {error}")
    finally:
        conn.close()


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

    # Geçmiş, agent'ın trend/öneri takibi için zamanla birikir.
    save_daily_snapshots()

    # Autopilot (sadece öneri): geçmiş önerilerin sonucunu raporlar ve bugünkü
    # kapatılmaya adayları izlemeye alır. Hesabı DEĞİŞTİRMEZ.
    try:
        autopilot = build_autopilot_section()
    except Exception as error:  # noqa: BLE001 — rapor yine de gitsin
        print(f"Autopilot bölümü oluşturulamadı: {error}")
        autopilot = ""

    today = date.today().isoformat()
    # E-posta: uyarılar → autopilot (öneri takibi) → tam yönetici özeti.
    sections = [format_alerts(alerts)]
    if autopilot:
        sections.append(autopilot)
    sections.append(summary)
    body = f"\n\n{'=' * 60}\n\n".join(sections)
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
