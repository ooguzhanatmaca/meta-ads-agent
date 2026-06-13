"""CLI for a consolidated, read-only Meta executive summary."""

from typing import Any

from app.meta.client import (
    MetaAPIError,
    get_account_insights_for_period,
    get_performance_report,
)
from app.meta.compare_periods import (
    PeriodComparison,
    build_default_periods,
    calculate_period_metrics,
    compare_metrics,
    format_comparison,
)
from app.meta.performance_report import calculate_report_rows
from app.meta.recommendations import format_recommendations
from app.rules.performance_rules import evaluate_ads


def select_best_ads(ads: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Select strongest ads by ROAS, purchases, and spend."""
    return sorted(
        ads,
        key=lambda ad: (ad["roas"], ad["purchases"], ad["spend"]),
        reverse=True,
    )[:limit]


def select_worst_ads(ads: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Select weakest ads by low ROAS and then high spend."""
    return sorted(ads, key=lambda ad: (ad["roas"], -ad["spend"]))[:limit]


def filter_recommendations(
    recommendations: list[dict[str, Any]], label: str
) -> list[dict[str, Any]]:
    return [item for item in recommendations if item["recommendation"] == label]


def format_today_summary(metrics: dict[str, float]) -> str:
    """Format today's account metrics without duplicating calculations."""
    return "\n".join(
        (
            "1. Bugünkü hesap özeti",
            f"Harcama: {metrics['spend']:.2f}",
            f"Gösterim: {metrics['impressions']:.0f}",
            f"Erişim: {metrics['reach']:.0f}",
            f"Tıklama: {metrics['clicks']:.0f}",
            f"CTR: %{metrics['ctr']:.2f}",
            f"CPC: {metrics['cpc']:.2f}",
            f"CPM: {metrics['cpm']:.2f}",
            f"Frekans: {metrics['frequency']:.2f}",
            f"Satın alma: {metrics['purchases']:.0f}",
            f"Satın alma değeri: {metrics['purchase_value']:.2f}",
            f"CPA: {metrics['cpa']:.2f}",
            f"ROAS: {metrics['roas']:.2f}",
        )
    )


def format_ad_list(title: str, ads: list[dict[str, Any]]) -> str:
    """Format a compact ranked ad list."""
    if not ads:
        return f"{title}\nKayıt bulunamadı."

    lines = [title]
    for index, ad in enumerate(ads, start=1):
        lines.append(
            f"{index}. {ad['name']} | Harcama: {ad['spend']:.2f} | "
            f"Satın alma: {ad['purchases']:.0f} | CPA: {ad['cpa']:.2f} | "
            f"ROAS: {ad['roas']:.2f} | Frekans: {ad['frequency']:.2f}"
        )
    return "\n".join(lines)


def format_action_section(
    title: str, recommendations: list[dict[str, Any]]
) -> str:
    if not recommendations:
        return f"{title}\nEşleşen reklam bulunamadı."
    return f"{title}\n{format_recommendations(recommendations)}"


def build_comparison(
    period: PeriodComparison,
    current: dict[str, float],
    previous: dict[str, float],
) -> str:
    return format_comparison(period, compare_metrics(current, previous))


def build_executive_summary() -> str:
    """Fetch data and assemble the full executive summary as a single string."""
    today_period, _, seven_day_period = build_default_periods()

    today_insight = get_account_insights_for_period(
        str(today_period.current_since), str(today_period.current_until)
    )
    yesterday_insight = get_account_insights_for_period(
        str(today_period.previous_since), str(today_period.previous_until)
    )
    seven_day_insight = get_account_insights_for_period(
        str(seven_day_period.current_since), str(seven_day_period.current_until)
    )
    previous_seven_day_insight = get_account_insights_for_period(
        str(seven_day_period.previous_since), str(seven_day_period.previous_until)
    )
    ad_entities = get_performance_report("ad", "last_7d")

    today_metrics = calculate_period_metrics(today_insight)
    yesterday_metrics = calculate_period_metrics(yesterday_insight)
    seven_day_metrics = calculate_period_metrics(seven_day_insight)
    previous_seven_day_metrics = calculate_period_metrics(
        previous_seven_day_insight
    )
    ads = calculate_report_rows(ad_entities)
    recommendations = evaluate_ads(ads)

    sections = (
        "META ADS YÖNETİCİ ÖZETİ",
        format_today_summary(today_metrics),
        "2. " + build_comparison(today_period, today_metrics, yesterday_metrics),
        "3. "
        + build_comparison(
            seven_day_period, seven_day_metrics, previous_seven_day_metrics
        ),
        format_ad_list("4. En iyi 5 reklam", select_best_ads(ads)),
        format_ad_list("5. En kötü 5 reklam", select_worst_ads(ads)),
        format_action_section(
            "6. Kapatılmaya aday reklamlar",
            filter_recommendations(recommendations, "Kapatılmaya aday"),
        ),
        format_action_section(
            "7. Bütçe artırılmaya aday reklamlar",
            filter_recommendations(recommendations, "Bütçeyi kontrollü artır"),
        ),
        format_action_section(
            "8. Kreatif yorgunluğu olan reklamlar",
            filter_recommendations(recommendations, "Kreatif değiştir"),
        ),
        format_action_section(
            "9. Öncelik sırasına göre aksiyon listesi", recommendations
        ),
    )
    return "\n\n".join(sections)


def main() -> int:
    try:
        print(build_executive_summary())
    except MetaAPIError as error:
        print(f"Yönetici özeti oluşturulamadı: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
