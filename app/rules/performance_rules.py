"""Deterministic rules for Meta ad performance recommendations."""

from typing import Any


PRIORITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def _recommendation(
    ad: dict[str, Any], recommendation: str, reason: str, priority: str
) -> dict[str, Any]:
    return {
        "id": str(ad.get("id") or "-"),
        "name": ad.get("name") or "-",
        "spend": float(ad.get("spend") or 0),
        "purchases": float(ad.get("purchases") or 0),
        "cpa": float(ad.get("cpa") or 0),
        "roas": float(ad.get("roas") or 0),
        "frequency": float(ad.get("frequency") or 0),
        "recommendation": recommendation,
        "reason": reason,
        "priority": priority,
    }


def evaluate_ad(ad: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every recommendation matched by one calculated ad row."""
    spend = float(ad.get("spend") or 0)
    purchases = float(ad.get("purchases") or 0)
    cpa = float(ad.get("cpa") or 0)
    roas = float(ad.get("roas") or 0)
    frequency = float(ad.get("frequency") or 0)
    ctr = float(ad.get("ctr") or 0)
    recommendations = []

    if spend >= 1000 and purchases == 0:
        recommendations.append(
            _recommendation(
                ad,
                "Kapatılmaya aday",
                f"Harcama {spend:.2f}, satın alma bulunmuyor.",
                "critical",
            )
        )

    if roas < 1.5 and spend >= 1500:
        recommendations.append(
            _recommendation(
                ad,
                "Bütçeyi azalt veya reklamı kapat",
                f"ROAS {roas:.2f} ve harcama {spend:.2f}.",
                "high",
            )
        )

    if cpa > 500 and purchases >= 2:
        recommendations.append(
            _recommendation(
                ad,
                "CPA yüksek",
                f"CPA {cpa:.2f}, {purchases:.0f} satın alma ile sınırın üzerinde.",
                "high",
            )
        )

    if frequency >= 3.5 and ctr < 1.0:
        recommendations.append(
            _recommendation(
                ad,
                "Kreatif değiştir",
                f"Frekans {frequency:.2f}, CTR %{ctr:.2f}; kreatif yorgunluğu riski var.",
                "medium",
            )
        )

    if roas >= 4 and purchases >= 5 and frequency < 3.5:
        recommendations.append(
            _recommendation(
                ad,
                "Bütçeyi kontrollü artır",
                f"ROAS {roas:.2f}, {purchases:.0f} satın alma ve frekans {frequency:.2f}.",
                "medium",
            )
        )

    if spend < 500:
        recommendations.append(
            _recommendation(
                ad,
                "Yetersiz veri, izlemeye devam et",
                f"Harcama {spend:.2f}; değerlendirme için veri henüz sınırlı.",
                "low",
            )
        )

    if roas >= 2.5 and cpa <= 400:
        recommendations.append(
            _recommendation(
                ad,
                "İyi performans",
                f"ROAS {roas:.2f} ve CPA {cpa:.2f} hedef aralıkta.",
                "low",
            )
        )

    return recommendations


def evaluate_ads(ads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate all ads and sort recommendations by priority and spend."""
    recommendations = [item for ad in ads for item in evaluate_ad(ad)]
    return sorted(
        recommendations,
        key=lambda item: (PRIORITY_ORDER[item["priority"]], -item["spend"]),
    )
