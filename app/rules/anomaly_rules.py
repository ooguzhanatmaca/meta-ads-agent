"""Deterministic anomaly detection for Meta ad performance.

Read-only: produces alerts only — never changes anything. Thresholds default to
sensible values and can be overridden with environment variables.
"""

import os
from dataclasses import dataclass
from typing import Any

from app.meta.compare_periods import percentage_change


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Eşikler (.env ile değiştirilebilir).
CPA_INCREASE_PCT = _env_float("ALERT_CPA_INCREASE_PCT", 25.0)
ROAS_DROP_PCT = _env_float("ALERT_ROAS_DROP_PCT", 20.0)
ROAS_FLOOR = _env_float("ALERT_ROAS_FLOOR", 2.0)
FREQUENCY_MAX = _env_float("ALERT_FREQUENCY", 3.5)
ZERO_SALE_SPEND = _env_float("ALERT_ZERO_SALE_SPEND", 500.0)
LOW_ROAS_SPEND = _env_float("ALERT_LOW_ROAS_SPEND", 300.0)
FREQUENCY_MIN_SPEND = _env_float("ALERT_FREQUENCY_MIN_SPEND", 200.0)
SPEND_PACING_PCT = _env_float("ALERT_SPEND_PACING_PCT", 50.0)

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Alert:
    """A single read-only anomaly finding."""

    severity: str  # "high" | "medium" | "low"
    scope: str  # "Hesap" | "Kampanya" | "Reklam"
    name: str
    message: str


def _f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def detect_account_anomalies(
    current: dict[str, Any], previous: dict[str, Any], label: str = "Son 7 gün"
) -> list[Alert]:
    """Flag account-level trend problems (CPA spike, ROAS drop/floor)."""
    alerts: list[Alert] = []
    cpa_c, cpa_p = _f(current.get("cpa")), _f(previous.get("cpa"))
    if cpa_p > 0 and cpa_c > 0:
        change = percentage_change(cpa_c, cpa_p)
        if change >= CPA_INCREASE_PCT:
            alerts.append(
                Alert(
                    "high",
                    "Hesap",
                    label,
                    f"CPA %{change:.0f} arttı ({cpa_p:.0f} → {cpa_c:.0f} TL).",
                )
            )

    roas_c, roas_p = _f(current.get("roas")), _f(previous.get("roas"))
    if roas_p > 0:
        change = percentage_change(roas_c, roas_p)
        if change <= -ROAS_DROP_PCT:
            alerts.append(
                Alert(
                    "high",
                    "Hesap",
                    label,
                    f"ROAS %{abs(change):.0f} düştü ({roas_p:.2f} → {roas_c:.2f}).",
                )
            )
    if 0 < roas_c < ROAS_FLOOR:
        alerts.append(
            Alert(
                "high",
                "Hesap",
                label,
                f"ROAS {roas_c:.2f} ile {ROAS_FLOOR:.1f} eşiğinin altında.",
            )
        )
    return alerts


def detect_pacing_anomaly(
    today_metrics: dict[str, Any], window_metrics: dict[str, Any], window_days: int = 7
) -> list[Alert]:
    """Flag if today's spend is well above the recent average daily spend."""
    today_spend = _f(today_metrics.get("spend"))
    avg_daily = _f(window_metrics.get("spend")) / window_days if window_days else 0.0
    if avg_daily <= 0:
        return []
    change = percentage_change(today_spend, avg_daily)
    if change >= SPEND_PACING_PCT:
        return [
            Alert(
                "medium",
                "Hesap",
                "Harcama temposu",
                f"Bugünkü harcama 7 günlük ortalamanın %{change:.0f} üzerinde "
                f"(₺{today_spend:,.0f} vs ₺{avg_daily:,.0f}/gün).",
            )
        ]
    return []


def detect_entity_anomalies(
    rows: list[dict[str, Any]], scope: str = "Reklam", limit: int = 15
) -> list[Alert]:
    """Flag per-entity problems: zero-sale spend, low ROAS, creative fatigue."""
    alerts: list[Alert] = []
    for row in rows:
        spend = _f(row.get("spend"))
        purchases = _f(row.get("purchases"))
        roas = _f(row.get("roas"))
        frequency = _f(row.get("frequency"))
        name = str(row.get("name") or "-")

        if spend >= ZERO_SALE_SPEND and purchases == 0:
            alerts.append(
                Alert("high", scope, name, f"₺{spend:,.0f} harcandı, satın alma yok.")
            )
        elif roas < ROAS_FLOOR and spend >= LOW_ROAS_SPEND and purchases > 0:
            alerts.append(
                Alert(
                    "high",
                    scope,
                    name,
                    f"ROAS {roas:.2f} (düşük), ₺{spend:,.0f} harcama — verimsiz.",
                )
            )

        if frequency >= FREQUENCY_MAX and spend >= FREQUENCY_MIN_SPEND:
            alerts.append(
                Alert(
                    "medium",
                    scope,
                    name,
                    f"Frekans {frequency:.2f} — kreatif yorgunluğu riski.",
                )
            )

    return sort_alerts(alerts)[:limit]


def sort_alerts(alerts: list[Alert]) -> list[Alert]:
    """Order alerts by severity (high first)."""
    return sorted(alerts, key=lambda a: SEVERITY_ORDER.get(a.severity, 3))
