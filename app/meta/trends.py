"""Historical daily trends for the Meta ad account.

Pulls daily account insights from Meta (no waiting for snapshots to accumulate),
computes per-metric trends, and renders a tiny terminal sparkline plus a plain
Turkish interpretation. Read-only.
"""

from datetime import date, timedelta
from typing import Any

from app.meta.account_summary import calculate_summary
from app.meta.client import get_account_daily_insights
from app.meta.compare_periods import percentage_change


SPARK_CHARS = "▁▂▃▄▅▆▇█"

METRIC_LABELS = {
    "spend": "Harcama",
    "roas": "ROAS",
    "cpa": "CPA",
    "ctr": "CTR",
    "cpc": "CPC",
    "cpm": "CPM",
    "purchases": "Satın alma",
    "purchase_value": "Satın alma değeri",
    "clicks": "Tıklama",
    "impressions": "Gösterim",
    "frequency": "Frekans",
}

# Türkçe/İngilizce metrik adı -> dahili anahtar.
METRIC_ALIASES = {
    "roas": "roas",
    "cpa": "cpa",
    "ctr": "ctr",
    "cpc": "cpc",
    "cpm": "cpm",
    "harcama": "spend",
    "spend": "spend",
    "satın alma": "purchases",
    "satin alma": "purchases",
    "purchases": "purchases",
    "gösterim": "impressions",
    "gosterim": "impressions",
    "tıklama": "clicks",
    "tiklama": "clicks",
    "frekans": "frequency",
    "frequency": "frequency",
}

HIGHER_IS_BETTER = {"roas", "ctr", "purchases", "purchase_value", "clicks", "impressions"}
LOWER_IS_BETTER = {"cpa", "cpc"}

DEFAULT_OVERVIEW_METRICS = ("roas", "cpa", "spend", "purchases")


def _date_range(days: int, today: date | None = None) -> tuple[date, date]:
    end = today or date.today()
    start = end - timedelta(days=max(1, days) - 1)
    return start, end


def daily_series_for_range(since: str, until: str) -> list[dict[str, Any]]:
    """Return chronological daily account metrics for an explicit date range."""
    rows = get_account_daily_insights(str(since), str(until))
    series: list[dict[str, Any]] = []
    for row in rows:
        metrics = calculate_summary(row)
        reach = metrics["reach"]
        metrics["frequency"] = metrics["impressions"] / reach if reach else 0.0
        metrics["date"] = row.get("date_start")
        series.append(metrics)
    series.sort(key=lambda item: item.get("date") or "")
    return series


def daily_series(days: int = 14, today: date | None = None) -> list[dict[str, Any]]:
    """Return a chronological list of daily account metrics for the last N days."""
    start, end = _date_range(days, today)
    return daily_series_for_range(str(start), str(end))


def sparkline(values: list[float]) -> str:
    """Render numbers as a compact unicode sparkline."""
    nums = [float(v or 0) for v in values]
    if not nums:
        return ""
    low, high = min(nums), max(nums)
    if high == low:
        return SPARK_CHARS[0] * len(nums)
    span = high - low
    return "".join(
        SPARK_CHARS[int((n - low) / span * (len(SPARK_CHARS) - 1))] for n in nums
    )


def summarize_metric(series: list[dict[str, Any]], metric: str) -> dict[str, Any] | None:
    """Compare the recent half vs the earlier half and classify the movement."""
    values = [float(d.get(metric) or 0) for d in series]
    if len(values) < 2:
        return None

    half = len(values) // 2 or 1
    earlier = sum(values[:half]) / half
    recent = sum(values[half:]) / (len(values) - half)
    change = percentage_change(recent, earlier)

    if metric in HIGHER_IS_BETTER:
        verdict = "iyileşiyor 👍" if recent > earlier else "kötüleşiyor ⚠️" if recent < earlier else "sabit"
    elif metric in LOWER_IS_BETTER:
        verdict = "iyileşiyor 👍" if recent < earlier else "kötüleşiyor ⚠️" if recent > earlier else "sabit"
    else:
        verdict = "artıyor" if recent > earlier else "azalıyor" if recent < earlier else "sabit"

    return {
        "metric": metric,
        "label": METRIC_LABELS.get(metric, metric),
        "values": values,
        "first": values[0],
        "last": values[-1],
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "change": change,
        "verdict": verdict,
        "sparkline": sparkline(values),
    }


def format_metric_trend(summary: dict[str, Any]) -> str:
    """One readable block for a single metric trend."""
    return "\n".join(
        (
            f"{summary['label']}: {summary['sparkline']}",
            f"  Son: {summary['last']:.2f} | Ort: {summary['avg']:.2f} | "
            f"Min-Max: {summary['min']:.2f}-{summary['max']:.2f}",
            f"  Eğilim: {summary['verdict']} (son yarı, önceki yarıya göre %{summary['change']:+.0f})",
        )
    )


def build_trend_report(metric: str = "özet", days: int = 14) -> str:
    """Fetch daily data and format the trend(s) for one metric or an overview."""
    series = daily_series(days)
    if len(series) < 2:
        return "Trend için yeterli günlük veri bulunamadı."

    period = f"Son {len(series)} gün"
    key = METRIC_ALIASES.get(metric.strip().lower())
    if key is None:
        metrics = DEFAULT_OVERVIEW_METRICS
        title = f"Trend özeti ({period})"
    else:
        metrics = (key,)
        title = f"{METRIC_LABELS.get(key, key)} trendi ({period})"

    blocks = []
    for m in metrics:
        summary = summarize_metric(series, m)
        if summary:
            blocks.append(format_metric_trend(summary))
    return f"{title}\n\n" + "\n\n".join(blocks)
