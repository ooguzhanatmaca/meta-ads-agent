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


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _action_metric(value: Any) -> float:
    if not isinstance(value, list):
        return 0.0
    return sum(
        _number(item.get("value"))
        for item in value
        if isinstance(item, dict)
    )


def _creative_type(creative: dict[str, Any]) -> str:
    object_type = str(creative.get("object_type") or "").upper()
    if creative.get("video_id") or "VIDEO" in object_type:
        return "Video"
    if "CAROUSEL" in object_type:
        return "Dönen Görsel"
    return "Görsel"


def calculate_report_rows(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten entity insights and calculate stable derived metrics."""
    rows = []
    for entity in entities:
        campaign = entity.get("campaign")
        adset = entity.get("adset")
        creative = entity.get("creative")
        if not isinstance(creative, dict):
            creative = {}
        insights = entity.get("insights")
        insight_data = insights.get("data") if isinstance(insights, dict) else None
        insight = insight_data[0] if isinstance(insight_data, list) and insight_data else {}
        if not isinstance(insight, dict):
            insight = {}

        metrics = calculate_summary(insight)
        reach = metrics["reach"]
        video_plays = _action_metric(insight.get("video_play_actions"))
        video_p25 = _action_metric(insight.get("video_p25_watched_actions"))
        video_p50 = _action_metric(insight.get("video_p50_watched_actions"))
        video_p75 = _action_metric(insight.get("video_p75_watched_actions"))
        video_p95 = _action_metric(insight.get("video_p95_watched_actions"))
        video_thruplays = _action_metric(
            insight.get("video_thruplay_watched_actions")
        )
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
                "creative_id": str(creative.get("id") or "-"),
                "creative_name": str(creative.get("name") or "-"),
                "creative_type": _creative_type(creative),
                "thumbnail_url": str(
                    creative.get("thumbnail_url")
                    or creative.get("image_url")
                    or ""
                ),
                **metrics,
                "frequency": metrics["impressions"] / reach if reach else 0.0,
                "video_plays": video_plays,
                "video_p25": video_p25,
                "video_p50": video_p50,
                "video_p75": video_p75,
                "video_p95": video_p95,
                "video_thruplays": video_thruplays,
                "video_hook_rate": (
                    video_plays / metrics["impressions"] * 100
                    if metrics["impressions"]
                    else 0.0
                ),
                "video_hold_rate": (
                    video_p75 / video_plays * 100 if video_plays else 0.0
                ),
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
