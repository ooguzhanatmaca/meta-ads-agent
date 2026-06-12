"""Data preparation for the local Meta Ads Streamlit dashboard."""

from datetime import date, timedelta
from io import BytesIO
from typing import Any

import pandas as pd

from app.meta.client import (
    get_account_insights_for_period,
    get_performance_report_for_period,
)
from app.meta.compare_periods import calculate_period_metrics, compare_metrics
from app.meta.export_excel import build_workbook
from app.meta.performance_report import calculate_report_rows
from app.rules.performance_rules import evaluate_ads
from app.rules.creative_rules import evaluate_creatives


TABLE_COLUMNS = {
    "id": "ID",
    "name": "Ad",
    "campaign_name": "Kampanya",
    "adset_name": "Reklam Seti",
    "status": "Durum",
    "spend": "Harcama",
    "impressions": "Gösterim",
    "reach": "Erişim",
    "clicks": "Tıklama",
    "ctr": "CTR",
    "cpc": "CPC",
    "cpm": "CPM",
    "frequency": "Frekans",
    "purchases": "Satın Alma",
    "purchase_value": "Satış Değeri",
    "cpa": "CPA",
    "roas": "ROAS",
}


def previous_period(start_date: date, end_date: date) -> tuple[date, date]:
    """Return the immediately preceding period with the same inclusive length."""
    days = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    return previous_end - timedelta(days=days - 1), previous_end


def load_dashboard_data(start_date: date, end_date: date) -> dict[str, Any]:
    """Load dashboard data through existing read-only Meta functions."""
    if start_date > end_date:
        raise ValueError("Başlangıç tarihi bitiş tarihinden sonra olamaz.")

    since = str(start_date)
    until = str(end_date)
    previous_start, previous_end = previous_period(start_date, end_date)
    current_metrics = calculate_period_metrics(
        get_account_insights_for_period(since, until)
    )
    previous_metrics = calculate_period_metrics(
        get_account_insights_for_period(
            str(previous_start),
            str(previous_end),
        )
    )
    campaigns = calculate_report_rows(
        get_performance_report_for_period("campaign", since, until)
    )
    adsets = calculate_report_rows(
        get_performance_report_for_period("adset", since, until)
    )
    ads = calculate_report_rows(
        get_performance_report_for_period("ad", since, until)
    )
    return {
        "current": current_metrics,
        "previous": previous_metrics,
        "comparison": compare_metrics(current_metrics, previous_metrics),
        "campaigns": campaigns,
        "adsets": adsets,
        "ads": ads,
        "recommendations": evaluate_ads(ads),
        "creatives": evaluate_creatives(ads),
        "start_date": start_date,
        "end_date": end_date,
        "previous_start": previous_start,
        "previous_end": previous_end,
    }


def rows_to_dataframe(
    rows: list[dict[str, Any]],
    columns: list[str],
) -> pd.DataFrame:
    """Convert calculated report rows into a stable display dataframe."""
    records = [{key: row.get(key, 0) for key in columns} for row in rows]
    return pd.DataFrame(records).rename(columns=TABLE_COLUMNS)


def recommendations_dataframe(
    recommendations: list[dict[str, Any]],
) -> pd.DataFrame:
    columns = [
        "name",
        "spend",
        "purchases",
        "cpa",
        "roas",
        "frequency",
        "recommendation",
        "reason",
        "priority",
    ]
    labels = {
        **TABLE_COLUMNS,
        "recommendation": "Öneri",
        "reason": "Gerekçe",
        "priority": "Öncelik",
    }
    records = [
        {key: item.get(key, "") for key in columns}
        for item in recommendations
    ]
    return pd.DataFrame(records).rename(columns=labels)


def dashboard_excel_bytes(data: dict[str, Any]) -> bytes:
    """Build an Excel download from already loaded dashboard data."""
    workbook_data = {
        "today": data["current"],
        "comparisons": [],
        "campaigns": data["campaigns"],
        "adsets": data["adsets"],
        "ads": data["ads"],
        "recommendations": data["recommendations"],
    }
    buffer = BytesIO()
    build_workbook(workbook_data).save(buffer)
    return buffer.getvalue()
