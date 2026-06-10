"""CLI for a read-only seven-day Meta account performance summary."""

from typing import Any

from app.meta.client import MetaAPIError, get_account_insights


PURCHASE_ACTION_TYPES = (
    "purchase",
    "omni_purchase",
    "offsite_conversion.fb_pixel_purchase",
    "onsite_web_purchase",
    "offsite_conversion.purchase",
    "offline_conversion.purchase",
)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _action_value(actions: Any) -> float:
    if not isinstance(actions, list):
        return 0.0

    values = {
        item.get("action_type"): _number(item.get("value"))
        for item in actions
        if isinstance(item, dict)
    }
    for action_type in PURCHASE_ACTION_TYPES:
        if action_type in values:
            return values[action_type]
    return 0.0


def calculate_summary(insight: dict[str, Any]) -> dict[str, float]:
    """Calculate stable performance metrics from one account insight row."""
    spend = _number(insight.get("spend"))
    impressions = _number(insight.get("impressions"))
    reach = _number(insight.get("reach"))
    clicks = _number(insight.get("clicks"))
    purchases = _action_value(insight.get("actions"))
    purchase_value = _action_value(insight.get("action_values"))

    return {
        "spend": spend,
        "impressions": impressions,
        "reach": reach,
        "clicks": clicks,
        "ctr": clicks / impressions * 100 if impressions else 0.0,
        "cpc": spend / clicks if clicks else 0.0,
        "cpm": spend / impressions * 1000 if impressions else 0.0,
        "purchases": purchases,
        "purchase_value": purchase_value,
        "cpa": spend / purchases if purchases else 0.0,
        "roas": purchase_value / spend if spend else 0.0,
    }


def format_summary(summary: dict[str, float]) -> str:
    """Format the calculated summary for terminal output."""
    return "\n".join(
        (
            "Meta hesap performansı - son 7 gün",
            f"Harcama: {summary['spend']:.2f}",
            f"Gösterim: {summary['impressions']:.0f}",
            f"Erişim: {summary['reach']:.0f}",
            f"Tıklama: {summary['clicks']:.0f}",
            f"CTR: %{summary['ctr']:.2f}",
            f"CPC: {summary['cpc']:.2f}",
            f"CPM: {summary['cpm']:.2f}",
            f"Satın alma: {summary['purchases']:.0f}",
            f"Satın alma değeri: {summary['purchase_value']:.2f}",
            f"CPA: {summary['cpa']:.2f}",
            f"ROAS: {summary['roas']:.2f}",
        )
    )


def main() -> int:
    try:
        summary = calculate_summary(get_account_insights("last_7d"))
        print(format_summary(summary))
    except MetaAPIError as error:
        print(f"Meta performans özeti alınamadı: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
