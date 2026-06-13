"""Root-cause ("neden?") analysis for the Meta ad account.

Gathers period-over-period evidence and likely causes, the entities dragging the
average, and a checklist of external factors the data cannot reveal. Read-only.
"""

from app.meta.client import get_account_insights_for_period, get_performance_report
from app.meta.compare_periods import build_default_periods, calculate_period_metrics
from app.meta.performance_report import calculate_report_rows
from app.rules.diagnosis_rules import (
    EXTERNAL_FACTORS,
    diagnose_account,
    diagnose_contributors,
)


def build_diagnosis() -> str:
    """Assemble a read-only root-cause analysis comparing the last 7 days to the prior 7."""
    _, _, period = build_default_periods()

    current = calculate_period_metrics(
        get_account_insights_for_period(
            str(period.current_since), str(period.current_until)
        )
    )
    previous = calculate_period_metrics(
        get_account_insights_for_period(
            str(period.previous_since), str(period.previous_until)
        )
    )

    causes = diagnose_account(current, previous)
    rows = calculate_report_rows(get_performance_report("campaign", "last_7d"))
    contributors = diagnose_contributors(rows, current.get("roas", 0.0))

    lines = [
        "KÖK NEDEN ANALİZİ (son 7 gün vs önceki 7 gün)",
        "",
        f"ROAS: {previous['roas']:.2f} → {current['roas']:.2f} | "
        f"CPA: {previous['cpa']:.0f} → {current['cpa']:.0f} | "
        f"Harcama: {previous['spend']:,.0f} → {current['spend']:,.0f}",
        "",
    ]

    if causes:
        lines.append("Olası nedenler (veriye dayalı):")
        for index, item in enumerate(causes, 1):
            lines.append(f"  {index}. {item['cause']} — {item['evidence']}")
    else:
        lines.append("Veriye dayalı belirgin bir olumsuz neden tespit edilmedi; hesap stabil.")

    if contributors:
        lines.append("")
        lines.append("Ortalamayı aşağı çeken varlıklar:")
        for item in contributors:
            lines.append(f"  - {item['name']}: {item['note']}")

    lines.append("")
    lines.append("Veriden görülemeyen, kontrol edilmesi gereken dış faktörler:")
    for factor in EXTERNAL_FACTORS:
        lines.append(f"  - {factor}")

    return "\n".join(lines)
