"""Read-only "what-if" simulation for Meta ad budget/pause scenarios.

Estimates account-level impact of scaling or pausing a campaign/ad set/ad,
assuming the entity's metrics scale linearly with spend. This is a projection,
not a guarantee — real scaling is non-linear. Nothing is changed on Meta.
"""

from typing import Any

from app.meta.client import get_performance_report
from app.meta.performance_report import calculate_report_rows


def _f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def account_totals(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate account-level totals/derived metrics from entity rows."""
    spend = sum(_f(r.get("spend")) for r in rows)
    purchases = sum(_f(r.get("purchases")) for r in rows)
    value = sum(_f(r.get("purchase_value")) for r in rows)
    clicks = sum(_f(r.get("clicks")) for r in rows)
    impressions = sum(_f(r.get("impressions")) for r in rows)
    return {
        "spend": spend,
        "purchases": purchases,
        "purchase_value": value,
        "clicks": clicks,
        "impressions": impressions,
        "roas": value / spend if spend else 0.0,
        "cpa": spend / purchases if purchases else 0.0,
    }


def _find(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    query = name.strip().lower()
    for row in rows:
        if str(row.get("name", "")).lower() == query:
            return row
    for row in rows:
        if query in str(row.get("name", "")).lower():
            return row
    return None


def simulate(
    rows: list[dict[str, Any]],
    target_name: str,
    change_pct: float = 0.0,
    pause: bool = False,
) -> dict[str, Any] | None:
    """Return before/after account totals for a scenario on one entity."""
    target = _find(rows, target_name)
    if target is None:
        return None

    before = account_totals(rows)

    if pause:
        new_rows = [r for r in rows if r is not target]
        action = "Kapatma"
    else:
        factor = 1 + change_pct / 100.0
        scaled = {
            **target,
            "spend": _f(target.get("spend")) * factor,
            "purchases": _f(target.get("purchases")) * factor,
            "purchase_value": _f(target.get("purchase_value")) * factor,
            "clicks": _f(target.get("clicks")) * factor,
            "impressions": _f(target.get("impressions")) * factor,
        }
        new_rows = [scaled if r is target else r for r in rows]
        action = f"Bütçe %{change_pct:+.0f}"

    after = account_totals(new_rows)
    return {
        "target": str(target.get("name", "-")),
        "action": action,
        "before": before,
        "after": after,
    }


def _delta(before: float, after: float) -> str:
    diff = after - before
    pct = (diff / before * 100) if before else 0.0
    return f"{after:,.2f} ({diff:+,.2f}, %{pct:+.1f})"


def format_simulation(result: dict[str, Any]) -> str:
    """Format a before/after simulation as readable text."""
    before, after = result["before"], result["after"]
    return "\n".join(
        (
            f"Senaryo: '{result['target']}' → {result['action']}",
            "(Tahmindir; gerçek ölçekleme doğrusal olmayabilir.)",
            "",
            f"Harcama: {before['spend']:,.2f} → {_delta(before['spend'], after['spend'])}",
            f"Satın alma: {before['purchases']:,.0f} → {_delta(before['purchases'], after['purchases'])}",
            f"Gelir: {before['purchase_value']:,.2f} → {_delta(before['purchase_value'], after['purchase_value'])}",
            f"ROAS: {before['roas']:.2f} → {_delta(before['roas'], after['roas'])}",
            f"CPA: {before['cpa']:.2f} → {_delta(before['cpa'], after['cpa'])}",
        )
    )


def build_simulation(
    target_name: str,
    change_pct: float = 0.0,
    pause: bool = False,
    level: str = "campaign",
    date_preset: str = "last_7d",
) -> str:
    """Fetch data and format a what-if scenario for one entity."""
    rows = calculate_report_rows(get_performance_report(level, date_preset))
    result = simulate(rows, target_name, change_pct, pause)
    if result is None:
        return f"'{target_name}' adlı {level} bulunamadı."
    return format_simulation(result)
