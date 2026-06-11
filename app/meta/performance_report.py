"""Shared calculations and terminal output for entity performance reports."""

from typing import Any

from app.meta.account_summary import calculate_summary
from app.meta.client import MetaAPIError, get_performance_report


HEADERS = (
    "ID",
    "Ad",
    "Durum",
    "Harcama",
    "Gösterim",
    "Erişim",
    "Tıklama",
    "CTR",
    "CPC",
    "CPM",
    "Frekans",
    "Satın Alma",
    "Satın Alma Değeri",
    "CPA",
    "ROAS",
)


def calculate_report_rows(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten entity insights and calculate stable derived metrics."""
    rows = []
    for entity in entities:
        campaign = entity.get("campaign")
        adset = entity.get("adset")
        insights = entity.get("insights")
        insight_data = insights.get("data") if isinstance(insights, dict) else None
        insight = insight_data[0] if isinstance(insight_data, list) and insight_data else {}
        if not isinstance(insight, dict):
            insight = {}

        metrics = calculate_summary(insight)
        reach = metrics["reach"]
        rows.append(
            {
                "id": str(entity.get("id") or "-"),
                "name": str(entity.get("name") or "-"),
                "campaign_name": str(
                    campaign.get("name") if isinstance(campaign, dict) else "-"
                ),
                "adset_name": str(
                    adset.get("name") if isinstance(adset, dict) else "-"
                ),
                "status": str(entity.get("status") or "-"),
                **metrics,
                "frequency": metrics["impressions"] / reach if reach else 0.0,
            }
        )

    return sorted(rows, key=lambda row: row["spend"], reverse=True)


def _cell(value: Any, width: int) -> str:
    text = str(value)
    if len(text) > width:
        text = f"{text[: width - 1]}…"
    return text.ljust(width)


def format_report(title: str, rows: list[dict[str, Any]]) -> str:
    """Format report rows as a readable fixed-width terminal table."""
    if not rows:
        return f"{title} - son 7 gün\nKayıt bulunamadı."

    widths = (14, 24, 10, 10, 11, 10, 9, 8, 8, 8, 9, 11, 17, 8, 8)
    table_rows = []
    for row in rows:
        values = (
            row["id"],
            row["name"],
            row["status"],
            f"{row['spend']:.2f}",
            f"{row['impressions']:.0f}",
            f"{row['reach']:.0f}",
            f"{row['clicks']:.0f}",
            f"%{row['ctr']:.2f}",
            f"{row['cpc']:.2f}",
            f"{row['cpm']:.2f}",
            f"{row['frequency']:.2f}",
            f"{row['purchases']:.0f}",
            f"{row['purchase_value']:.2f}",
            f"{row['cpa']:.2f}",
            f"{row['roas']:.2f}",
        )
        table_rows.append(" | ".join(_cell(value, width) for value, width in zip(values, widths)))

    header = " | ".join(_cell(value, width) for value, width in zip(HEADERS, widths))
    separator = "-+-".join("-" * width for width in widths)
    return "\n".join((f"{title} - son 7 gün", header, separator, *table_rows))


def run_report(level: str, title: str) -> int:
    """Fetch and print one read-only Meta performance report."""
    try:
        entities = get_performance_report(level, "last_7d")
        print(format_report(title, calculate_report_rows(entities)))
    except MetaAPIError as error:
        print(f"{title} alınamadı: {error}")
        return 1
    return 0
