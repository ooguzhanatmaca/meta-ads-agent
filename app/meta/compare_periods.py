"""CLI for deterministic Meta account period comparisons."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.meta.account_summary import calculate_summary
from app.meta.client import MetaAPIError, get_account_insights_for_period


METRICS = (
    "spend",
    "purchases",
    "purchase_value",
    "cpa",
    "roas",
    "ctr",
    "cpc",
    "cpm",
    "frequency",
)
METRIC_LABELS = {
    "spend": "Harcama",
    "purchases": "Satın alma",
    "purchase_value": "Satın alma değeri",
    "cpa": "CPA",
    "roas": "ROAS",
    "ctr": "CTR",
    "cpc": "CPC",
    "cpm": "CPM",
    "frequency": "Frekans",
}
HIGHER_IS_BETTER = {"purchases", "purchase_value", "roas", "ctr"}
LOWER_IS_BETTER = {"cpa", "cpc"}


@dataclass(frozen=True)
class PeriodComparison:
    title: str
    current_since: date
    current_until: date
    previous_since: date
    previous_until: date


def build_default_periods(today: date | None = None) -> list[PeriodComparison]:
    """Build the three default inclusive comparison ranges."""
    current_day = today or date.today()
    periods = []
    for title, days in (
        ("Bugün vs dün", 1),
        ("Son 3 gün vs önceki 3 gün", 3),
        ("Son 7 gün vs önceki 7 gün", 7),
    ):
        current_since = current_day - timedelta(days=days - 1)
        previous_until = current_since - timedelta(days=1)
        periods.append(
            PeriodComparison(
                title=title,
                current_since=current_since,
                current_until=current_day,
                previous_since=previous_until - timedelta(days=days - 1),
                previous_until=previous_until,
            )
        )
    return periods


def calculate_period_metrics(insight: dict[str, Any]) -> dict[str, float]:
    """Reuse account calculations and add a safe account frequency metric."""
    metrics = calculate_summary(insight)
    reach = metrics["reach"]
    return {
        **metrics,
        "frequency": metrics["impressions"] / reach if reach else 0.0,
    }


def percentage_change(current: float, previous: float) -> float:
    """Calculate a stable percentage change when the previous value is zero."""
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return (current - previous) / abs(previous) * 100


def direction(current: float, previous: float) -> str:
    if current > previous:
        return "arttı"
    if current < previous:
        return "azaldı"
    return "aynı"


def result_label(metric: str, current: float, previous: float) -> str:
    """Classify metric movement using deterministic business rules."""
    if current == previous:
        return "nötr"
    if metric in HIGHER_IS_BETTER:
        return "iyileşti" if current > previous else "kötüleşti"
    if metric in LOWER_IS_BETTER:
        return "iyileşti" if current < previous else "kötüleşti"
    if metric == "frequency":
        if current > 3.5 and current > previous:
            return "kötüleşti"
        if previous > 3.5 and current < previous:
            return "iyileşti"
    return "nötr"


def compare_metrics(
    current: dict[str, float], previous: dict[str, float]
) -> list[dict[str, Any]]:
    """Compare the requested metrics in stable display order."""
    comparisons = []
    for metric in METRICS:
        current_value = float(current.get(metric) or 0)
        previous_value = float(previous.get(metric) or 0)
        comparisons.append(
            {
                "metric": metric,
                "current": current_value,
                "previous": previous_value,
                "change": percentage_change(current_value, previous_value),
                "direction": direction(current_value, previous_value),
                "result": result_label(metric, current_value, previous_value),
            }
        )
    return comparisons


def _cell(value: Any, width: int) -> str:
    text = str(value)
    if len(text) > width:
        text = f"{text[: width - 1]}…"
    return text.ljust(width)


def format_comparison(
    period: PeriodComparison, comparisons: list[dict[str, Any]]
) -> str:
    """Format one period comparison as a terminal table."""
    headers = ("Metrik", "Mevcut", "Önceki", "Değişim", "Yön", "Sonuç")
    widths = (20, 12, 12, 11, 9, 12)
    lines = []
    for item in comparisons:
        values = (
            METRIC_LABELS[item["metric"]],
            f"{item['current']:.2f}",
            f"{item['previous']:.2f}",
            f"%{item['change']:+.2f}",
            item["direction"],
            item["result"],
        )
        lines.append(" | ".join(_cell(value, width) for value, width in zip(values, widths)))

    header = " | ".join(_cell(value, width) for value, width in zip(headers, widths))
    separator = "-+-".join("-" * width for width in widths)
    ranges = (
        f"Mevcut: {period.current_since} - {period.current_until} | "
        f"Önceki: {period.previous_since} - {period.previous_until}"
    )
    return "\n".join((period.title, ranges, header, separator, *lines))


def main() -> int:
    try:
        outputs = []
        for period in build_default_periods():
            current = get_account_insights_for_period(
                str(period.current_since), str(period.current_until)
            )
            previous = get_account_insights_for_period(
                str(period.previous_since), str(period.previous_until)
            )
            comparisons = compare_metrics(
                calculate_period_metrics(current),
                calculate_period_metrics(previous),
            )
            outputs.append(format_comparison(period, comparisons))
        print("\n\n".join(outputs))
    except MetaAPIError as error:
        print(f"Dönem karşılaştırması alınamadı: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
