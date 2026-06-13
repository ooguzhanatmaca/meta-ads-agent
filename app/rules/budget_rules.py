"""Deterministic, read-only budget suggestions from calculated entity rows.

Suggestions are advisory only — they never change budgets. Each suggestion
includes a proposed daily budget derived from the entity's recent average daily
spend over the report window (default 7 days).
"""

from typing import Any


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def budget_suggestion(row: dict[str, Any], window_days: int = 7) -> dict[str, Any]:
    """Return a single budget suggestion for one entity (campaign/adset/ad)."""
    spend = _number(row.get("spend"))
    roas = _number(row.get("roas"))
    purchases = _number(row.get("purchases"))
    frequency = _number(row.get("frequency"))
    cpa = _number(row.get("cpa"))

    daily_spend = spend / window_days if window_days else spend

    if roas >= 4 and purchases >= 5 and frequency < 3.0:
        action, pct, priority = "Bütçeyi artır", 25, "high"
        reason = f"ROAS {roas:.2f}, {purchases:.0f} satın alma, frekans {frequency:.2f} (düşük) — ölçeklenebilir."
    elif roas >= 2.5 and purchases >= 3 and frequency < 3.5:
        action, pct, priority = "Bütçeyi kontrollü artır", 10, "medium"
        reason = f"ROAS {roas:.2f}, {purchases:.0f} satın alma — kademeli artırılabilir."
    elif spend >= 500 and purchases == 0:
        action, pct, priority = "Durdur", -100, "high"
        reason = f"₺{spend:,.2f} harcamaya rağmen satın alma yok."
    elif roas < 1.5 and spend >= 300:
        action, pct, priority = "Bütçeyi azalt", -40, "high"
        reason = f"ROAS {roas:.2f} (düşük), ₺{spend:,.2f} harcama — verimsiz."
    elif frequency >= 4.0:
        action, pct, priority = "Bütçeyi azalt", -25, "medium"
        reason = f"Frekans {frequency:.2f} yüksek — kitle yorgunluğu riski."
    else:
        action, pct, priority = "Koru", 0, "low"
        reason = f"ROAS {roas:.2f}, frekans {frequency:.2f} — belirgin bir sinyal yok."

    suggested_daily = max(0.0, daily_spend * (1 + pct / 100))

    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "spend": spend,
        "roas": roas,
        "purchases": purchases,
        "frequency": frequency,
        "cpa": cpa,
        "current_daily": daily_spend,
        "action": action,
        "change_pct": pct,
        "suggested_daily": suggested_daily,
        "priority": priority,
        "reason": reason,
    }


def budget_suggestions(
    rows: list[dict[str, Any]], window_days: int = 7
) -> list[dict[str, Any]]:
    """Return budget suggestions ordered by priority then spend."""
    results = [budget_suggestion(row, window_days) for row in rows]
    return sorted(
        results,
        key=lambda item: (PRIORITY_ORDER[item["priority"]], -item["spend"]),
    )
