"""Collect and format read-only anomaly alerts for the Meta ad account."""

from app.meta.client import (
    get_account_insights_for_period,
    get_performance_report,
)
from app.meta.compare_periods import build_default_periods, calculate_period_metrics
from app.meta.performance_report import calculate_report_rows
from app.rules.anomaly_rules import (
    Alert,
    detect_account_anomalies,
    detect_entity_anomalies,
    detect_pacing_anomaly,
    sort_alerts,
)


SEVERITY_ICON = {"high": "🔴", "medium": "🟡", "low": "🔵"}


def collect_alerts() -> list[Alert]:
    """Fetch data and return all anomaly alerts, ordered by severity."""
    today_period, _, seven_day_period = build_default_periods()

    current = calculate_period_metrics(
        get_account_insights_for_period(
            str(seven_day_period.current_since), str(seven_day_period.current_until)
        )
    )
    previous = calculate_period_metrics(
        get_account_insights_for_period(
            str(seven_day_period.previous_since), str(seven_day_period.previous_until)
        )
    )
    today_metrics = calculate_period_metrics(
        get_account_insights_for_period(
            str(today_period.current_since), str(today_period.current_until)
        )
    )

    alerts: list[Alert] = []
    alerts += detect_account_anomalies(current, previous)
    alerts += detect_pacing_anomaly(today_metrics, current)

    ad_rows = calculate_report_rows(get_performance_report("ad", "last_7d"))
    alerts += detect_entity_anomalies(ad_rows, "Reklam")

    return sort_alerts(alerts)


def format_alerts(alerts: list[Alert]) -> str:
    """Format alerts as readable text (with a clear all-clear message)."""
    if not alerts:
        return "✅ Önemli bir sorun tespit edilmedi. Hesap normal seyrediyor."

    lines = [f"⚠️ {len(alerts)} uyarı tespit edildi:", ""]
    for alert in alerts:
        icon = SEVERITY_ICON.get(alert.severity, "•")
        lines.append(f"{icon} [{alert.scope}] {alert.name}: {alert.message}")
    return "\n".join(lines)


def build_anomaly_report() -> str:
    """Fetch, evaluate and format anomaly alerts in one call."""
    return format_alerts(collect_alerts())
