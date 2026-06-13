"""Smart weekly digest: this week vs last week + best/worst ads + alerts."""

from app.meta.anomaly_report import collect_alerts, format_alerts
from app.meta.client import get_account_insights_for_period, get_performance_report
from app.meta.compare_periods import (
    build_default_periods,
    calculate_period_metrics,
    compare_metrics,
    format_comparison,
)
from app.meta.executive_summary import (
    format_ad_list,
    select_best_ads,
    select_worst_ads,
)
from app.meta.performance_report import calculate_report_rows


def build_weekly_digest() -> str:
    """Assemble a read-only weekly digest as a single string."""
    _, _, seven_day_period = build_default_periods()

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
    comparison = compare_metrics(current, previous)

    ads = calculate_report_rows(get_performance_report("ad", "last_7d"))

    sections = (
        "HAFTALIK ÖZET",
        "1. " + format_comparison(seven_day_period, comparison),
        format_ad_list("2. En iyi 3 reklam", select_best_ads(ads, 3)),
        format_ad_list("3. En kötü 3 reklam", select_worst_ads(ads, 3)),
        "4. Uyarılar\n" + format_alerts(collect_alerts()),
    )
    return "\n\n".join(sections)
