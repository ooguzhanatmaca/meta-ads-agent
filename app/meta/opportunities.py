"""Build data-driven growth opportunities (the agent's strategic ideas)."""

from typing import Any

from app.meta.account_summary import calculate_summary
from app.meta.client import (
    get_account_insights,
    get_account_insights_breakdown,
    get_performance_report,
)
from app.meta.performance_report import calculate_report_rows
from app.rules.opportunity_rules import (
    best_segment,
    reallocation_candidates,
    scaling_candidate,
    underspending_winner,
)


def _summarize_breakdown(rows: list[dict[str, Any]], label_key: str) -> list[dict[str, Any]]:
    summarized = []
    for row in rows:
        metrics = calculate_summary(row)
        summarized.append(
            {
                "label": str(row.get(label_key) or "-"),
                "roas": metrics["roas"],
                "spend": metrics["spend"],
            }
        )
    return summarized


def collect_opportunities() -> list[dict[str, str]]:
    """Gather data and return a list of growth opportunities with suggested actions."""
    account = calculate_summary(get_account_insights("last_7d"))
    account_roas = account["roas"]

    age = _summarize_breakdown(get_account_insights_breakdown("age"), "age")
    placement = _summarize_breakdown(
        get_account_insights_breakdown("publisher_platform"), "publisher_platform"
    )
    campaigns = calculate_report_rows(get_performance_report("campaign", "last_7d"))
    adsets = calculate_report_rows(get_performance_report("adset", "last_7d"))

    opportunities: list[dict[str, str]] = []

    # 1. Yetersiz hedeflenen kazanan yaş segmenti
    seg = underspending_winner(age, account_roas) or best_segment(age, account_roas)
    if seg:
        opportunities.append({
            "baslik": f"{seg['label']} yaş grubuna ağırlık ver",
            "gerekce": f"ROAS {seg['roas']:.2f} (hesap ort. {account_roas:.2f}); harcaması görece düşük.",
            "oneri": f"Bu yaş grubunu hedefleyen ayrı bir reklam seti aç veya mevcut setlerde bu gruba bütçe kaydır.",
        })

    # 2. En verimli yerleşim
    best_place = best_segment(placement, account_roas, min_spend=200)
    if best_place:
        opportunities.append({
            "baslik": f"{best_place['label']} yerleşimini büyüt",
            "gerekce": f"ROAS {best_place['roas']:.2f} ile ortalamanın üzerinde.",
            "oneri": "Bu yerleşime daha fazla bütçe ayır veya yalnızca bu yerleşimi hedefleyen bir set test et.",
        })

    # 3. Bütçe yeniden dağıtımı
    scale_up, scale_down = reallocation_candidates(campaigns, account_roas)
    if scale_up and scale_down:
        up = scale_up[0]["name"]
        down = scale_down[0]["name"]
        opportunities.append({
            "baslik": "Bütçeyi verimliden verimsize doğru yeniden dağıt",
            "gerekce": f"'{up}' yüksek ROAS, düşük frekans; '{down}' düşük ROAS, yüksek harcama.",
            "oneri": f"'{down}' bütçesini azalt, '{up}' bütçesini artır (update_daily_budget ile).",
        })
    elif scale_up:
        up = scale_up[0]
        opportunities.append({
            "baslik": f"'{up['name']}' kampanyasını ölçekle",
            "gerekce": f"ROAS {up['roas']:.2f}, frekans {up['frequency']:.2f} (düşük) — büyütmeye uygun.",
            "oneri": "Bütçesini kademeli (%20-25) artır.",
        })

    # 4. Ölçeklemeye uygun reklam seti (klonlama adayı)
    candidate = scaling_candidate(adsets)
    if candidate:
        opportunities.append({
            "baslik": f"'{candidate['name']}' setini çoğalt",
            "gerekce": f"ROAS {candidate['roas']:.2f}, frekans {candidate['frequency']:.2f} — kazanan.",
            "oneri": "clone_ad_set_tool ile bu seti baz alıp (örn. %50 fazla bütçeyle) yeni bir set kur.",
        })

    # 5. Denenmemiş kitle fikri (her zaman geçerli strateji)
    opportunities.append({
        "baslik": "Satın alanlardan benzer kitle (lookalike) test et",
        "gerekce": "Mevcut müşterilere benzer yeni kullanıcılara ulaşmak ölçeklemenin temel yoludur.",
        "oneri": "Satın alma bazlı %1-3 lookalike kitle oluşturup en iyi kreatifinle test et.",
    })

    return opportunities


def format_opportunities(opportunities: list[dict[str, str]]) -> str:
    if not opportunities:
        return "Şu an veriye dayalı belirgin bir fırsat tespit edilmedi."
    lines = ["Büyüme fırsatları (öneriler):", ""]
    for index, opp in enumerate(opportunities, 1):
        lines.append(f"{index}. {opp['baslik']}")
        lines.append(f"   Gerekçe: {opp['gerekce']}")
        lines.append(f"   Öneri: {opp['oneri']}")
    return "\n".join(lines)


def build_opportunities() -> str:
    return format_opportunities(collect_opportunities())
