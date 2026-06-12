"""Rule-based creative analysis for calculated Meta ad rows."""

from typing import Any


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _result(
    ad: dict[str, Any],
    label: str,
    recommendation: str,
    reason: str,
    priority: str,
) -> dict[str, Any]:
    return {
        **ad,
        "creative_label": label,
        "creative_recommendation": recommendation,
        "creative_reason": reason,
        "creative_priority": priority,
    }


def evaluate_creative(ad: dict[str, Any]) -> dict[str, Any]:
    """Return the strongest deterministic creative recommendation for one ad."""
    spend = float(ad.get("spend") or 0)
    purchases = float(ad.get("purchases") or 0)
    roas = float(ad.get("roas") or 0)
    ctr = float(ad.get("ctr") or 0)
    frequency = float(ad.get("frequency") or 0)
    creative_type = str(ad.get("creative_type") or "Görsel")
    video_plays = float(ad.get("video_plays") or 0)
    hook_rate = float(ad.get("video_hook_rate") or 0)
    hold_rate = float(ad.get("video_hold_rate") or 0)

    if spend >= 1000 and purchases == 0:
        return _result(
            ad,
            "Bu kreatif çalışmıyor",
            "Konsepti, ana mesajı ve görsel/video açısını değiştir.",
            f"₺{spend:,.2f} harcamaya rağmen satın alma oluşmadı.",
            "critical",
        )

    if frequency >= 3.5 and ctr < 1.0:
        change = "ilk kareyi ve açılışı" if creative_type == "Video" else "görseli"
        return _result(
            ad,
            "Kreatif yoruldu",
            f"Aynı teklif korunarak {change} değiştir.",
            f"Frekans {frequency:.2f}, CTR %{ctr:.2f}; kitle aynı kreatifi fazla görüyor.",
            "high",
        )

    if roas >= 4 and purchases >= 5 and frequency < 3.5:
        if creative_type == "Video" and video_plays > 0 and hook_rate < 20:
            variation = (
                "Kazanan yapıyı koru; ölçeklemeden önce hook / ilk 3 "
                "saniyenin yeni bir varyasyonunu üret."
            )
        elif creative_type == "Video":
            variation = (
                "Aynı yapıyı koruyup yeni hook, ilk kare ve süre "
                "varyasyonları üret."
            )
        else:
            variation = (
                "Aynı konseptin başlık, renk ve ürün kadrajı "
                "varyasyonlarını üret."
            )
        return _result(
            ad,
            "Bu kreatif tuttu",
            variation,
            f"ROAS {roas:.2f}, {purchases:.0f} satın alma ve frekans {frequency:.2f}.",
            "low",
        )

    if creative_type == "Video" and spend >= 500 and video_plays > 0 and hook_rate < 20:
        return _result(
            ad,
            "Video açılışı zayıf",
            "İlk 3 saniyeyi değiştir; sonucu veya güçlü vaadi ilk karede göster.",
            f"Video başlatma oranı %{hook_rate:.2f} ile düşük.",
            "high",
        )

    if creative_type == "Video" and spend >= 500 and video_plays > 0 and hold_rate < 25:
        return _result(
            ad,
            "Video izleyiciyi tutmuyor",
            "Videoyu kısalt; ürün ve faydayı daha erken göster.",
            f"İzleyenlerin yalnızca %{hold_rate:.2f} kadarı videonun %75'ine ulaştı.",
            "medium",
        )

    if ctr >= 1.5 and purchases == 0 and spend >= 500:
        return _result(
            ad,
            "İlgi var, dönüşüm zayıf",
            "Kreatifi koru; teklif, ürün sayfası ve mesaj uyumunu kontrol et.",
            f"CTR %{ctr:.2f} olmasına rağmen satın alma oluşmadı.",
            "medium",
        )

    return _result(
        ad,
        "İzlemeye devam et",
        "Yeni karar için daha fazla veri topla ve mevcut varyasyonu koru.",
        f"Harcama ₺{spend:,.2f}; güçlü bir kreatif sinyali henüz oluşmadı.",
        "low",
    )


def evaluate_creatives(ads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Analyze ads and order urgent creative actions before winners."""
    results = [evaluate_creative(ad) for ad in ads]
    return sorted(
        results,
        key=lambda item: (
            PRIORITY_ORDER[item["creative_priority"]],
            -float(item.get("spend") or 0),
        ),
    )
