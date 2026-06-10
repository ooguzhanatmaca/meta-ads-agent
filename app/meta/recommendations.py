"""CLI for deterministic, read-only Meta ad recommendations."""

from typing import Any

from app.meta.client import MetaAPIError, get_performance_report
from app.meta.performance_report import calculate_report_rows
from app.rules.performance_rules import evaluate_ads


HEADERS = (
    "Reklam",
    "Harcama",
    "Satın Alma",
    "CPA",
    "ROAS",
    "Frekans",
    "Öncelik",
    "Öneri",
    "Gerekçe",
)


def _cell(value: Any, width: int) -> str:
    text = str(value)
    if len(text) > width:
        text = f"{text[: width - 1]}…"
    return text.ljust(width)


def format_recommendations(recommendations: list[dict[str, Any]]) -> str:
    """Format recommendations as a readable terminal table."""
    title = "Kural tabanlı reklam önerileri - son 7 gün"
    if not recommendations:
        return f"{title}\nEşleşen öneri bulunamadı."

    widths = (22, 10, 11, 9, 8, 9, 9, 31, 58)
    lines = []
    for item in recommendations:
        values = (
            item["name"],
            f"{item['spend']:.2f}",
            f"{item['purchases']:.0f}",
            f"{item['cpa']:.2f}",
            f"{item['roas']:.2f}",
            f"{item['frequency']:.2f}",
            item["priority"],
            item["recommendation"],
            item["reason"],
        )
        lines.append(" | ".join(_cell(value, width) for value, width in zip(values, widths)))

    header = " | ".join(_cell(value, width) for value, width in zip(HEADERS, widths))
    separator = "-+-".join("-" * width for width in widths)
    return "\n".join((title, header, separator, *lines))


def main() -> int:
    try:
        entities = get_performance_report("ad", "last_7d")
        ad_rows = calculate_report_rows(entities)
        print(format_recommendations(evaluate_ads(ad_rows)))
    except MetaAPIError as error:
        print(f"Reklam önerileri oluşturulamadı: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
