"""Rule-based creative analysis for calculated Meta ad rows."""

from typing import Any


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def creative_health(ad: dict[str, Any]) -> tuple[int, str]:
    """Calculate a bounded creative health score from stable ad metrics."""
    spend = float(ad.get("spend") or 0)
    purchases = float(ad.get("purchases") or 0)
    roas = float(ad.get("roas") or 0)
    ctr = float(ad.get("ctr") or 0)
    frequency = float(ad.get("frequency") or 0)
    score = 50

    score += 25 if roas >= 4 else 15 if roas >= 2.5 else -20 if spend >= 500 else 0
    score += 15 if ctr >= 2 else 5 if ctr >= 1 else -10
    score += 10 if purchases >= 5 else -20 if spend >= 1000 and purchases == 0 else 0
    score += 5 if frequency < 3.5 else -15
    score = max(0, min(100, score))
    status = "Sağlıklı" if score >= 75 else "Riskli" if score >= 45 else "Zayıf"
    return score, status


def build_creative_brief(ad: dict[str, Any]) -> dict[str, str]:
    """Build a local rule-based variation brief without an AI API call."""
    creative_type = str(ad.get("creative_type") or "Görsel")
    label = str(ad.get("creative_label") or "")
    roas = float(ad.get("roas") or 0)
    ctr = float(ad.get("ctr") or 0)

    if creative_type == "Video":
        hook = (
            "İlk karede sonucu göster ve ilk 3 saniyede net bir vaat kullan."
            if float(ad.get("video_hook_rate") or 0) < 20
            else "Mevcut açılışı koru; aynı vaadin daha kısa bir varyasyonunu dene."
        )
        format_note = "15-25 saniye, hızlı kurgu, ürün ilk 5 saniyede görünür."
    else:
        hook = "Ürünü tek odak yap; faydayı kısa ve yüksek kontrastlı başlıkla göster."
        format_note = "1:1 ve 4:5 varyasyon; temiz kadraj ve güçlü ürün yakın planı."

    angle = (
        "Kazanan mesajı koru, yalnızca hook ve görsel dili çeşitlendir."
        if label == "Bu kreatif tuttu"
        else "Yeni problem-çözüm açısı ve farklı bir kullanım senaryosu dene."
    )
    cta = "Şimdi incele" if roas >= 2.5 else "Detayları gör"
    proof = (
        "Müşteri yorumu veya kullanım sonucu ekle."
        if ctr < 1.5
        else "Mevcut ilgi güçlü; teklif ve ürün faydasını daha net bağla."
    )
    return {
        "hook": hook,
        "angle": angle,
        "format": format_note,
        "proof": proof,
        "cta": cta,
    }


def _result(
    ad: dict[str, Any],
    label: str,
    recommendation: str,
    reason: str,
    priority: str,
) -> dict[str, Any]:
    result = {
        **ad,
        "creative_label": label,
        "creative_recommendation": recommendation,
        "creative_reason": reason,
        "creative_priority": priority,
    }
    score, health_status = creative_health(result)
    result["health_score"] = score
    result["health_status"] = health_status
    result["creative_brief"] = build_creative_brief(result)
    return result


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
