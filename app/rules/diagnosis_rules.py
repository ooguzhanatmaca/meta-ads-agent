"""Deterministic root-cause heuristics for account-level metric changes.

Maps observed metric movements (period over period) to likely causes with
evidence. Read-only; never claims certainty about factors it cannot see.
"""

from typing import Any

from app.meta.compare_periods import percentage_change


# Hareketin "anlamlı" sayılması için eşikler (yüzde).
FREQ_UP = 15.0
CPM_UP = 15.0
CPC_UP = 15.0
CTR_DOWN = 10.0
PURCHASES_DOWN = 10.0
ROAS_DOWN = 10.0
CPA_UP = 10.0


def _f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _ch(current: dict[str, Any], previous: dict[str, Any], key: str) -> float:
    return percentage_change(_f(current.get(key)), _f(previous.get(key)))


def diagnose_account(current: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, str]]:
    """Return evidence-backed likely causes for the account's recent movement."""
    findings: list[dict[str, str]] = []

    roas_ch = _ch(current, previous, "roas")
    cpa_ch = _ch(current, previous, "cpa")
    value_ch = _ch(current, previous, "purchase_value")
    spend_ch = _ch(current, previous, "spend")
    purchases_ch = _ch(current, previous, "purchases")
    freq_ch = _ch(current, previous, "frequency")
    cpm_ch = _ch(current, previous, "cpm")
    cpc_ch = _ch(current, previous, "cpc")
    ctr_ch = _ch(current, previous, "ctr")

    # ROAS düşüşünün matematiksel ayrıştırması (gelir mi düştü, harcama mı arttı).
    if roas_ch <= -ROAS_DOWN:
        if value_ch <= -5:
            findings.append({
                "cause": "Gelir (satın alma değeri) düştü",
                "evidence": f"Satın alma değeri %{value_ch:+.0f} değişti; ROAS %{roas_ch:+.0f}.",
            })
        if spend_ch >= 5 and value_ch < spend_ch:
            findings.append({
                "cause": "Harcama gelirden hızlı arttı (ölçekleme verimsizliği)",
                "evidence": f"Harcama %{spend_ch:+.0f}, gelir %{value_ch:+.0f} — getiri aynı oranda artmadı.",
            })

    # CPA artışının ayrıştırması.
    if cpa_ch >= CPA_UP:
        if purchases_ch <= -5:
            findings.append({
                "cause": "Dönüşüm sayısı azaldı",
                "evidence": f"Satın alma %{purchases_ch:+.0f}; CPA %{cpa_ch:+.0f} arttı.",
            })
        if spend_ch >= 5 and purchases_ch < spend_ch:
            findings.append({
                "cause": "Harcama arttı ama dönüşüm aynı oranda artmadı",
                "evidence": f"Harcama %{spend_ch:+.0f}, satın alma %{purchases_ch:+.0f}.",
            })

    # Belirti tabanlı nedenler.
    if freq_ch >= FREQ_UP:
        findings.append({
            "cause": "Kreatif yorgunluğu / kitle doygunluğu",
            "evidence": f"Frekans %{freq_ch:+.0f} arttı — kitle aynı reklamı daha çok görüyor.",
        })
    if cpm_ch >= CPM_UP:
        findings.append({
            "cause": "Açık artırma rekabeti veya kitle daralması",
            "evidence": f"CPM (bin gösterim maliyeti) %{cpm_ch:+.0f} arttı.",
        })
    if ctr_ch <= -CTR_DOWN:
        findings.append({
            "cause": "Kreatif ilgisi azaldı / kitle uyumu zayıfladı",
            "evidence": f"CTR %{ctr_ch:+.0f} düştü.",
        })
    if cpc_ch >= CPC_UP and ctr_ch < 0:
        findings.append({
            "cause": "Tıklama maliyeti arttı (düşen CTR + rekabet)",
            "evidence": f"CPC %{cpc_ch:+.0f} arttı, CTR %{ctr_ch:+.0f} düştü.",
        })

    return findings


def diagnose_contributors(rows: list[dict[str, Any]], account_roas: float) -> list[dict[str, str]]:
    """Flag entities that drag the account average (current-period view)."""
    contributors: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda r: _f(r.get("spend")), reverse=True):
        spend = _f(row.get("spend"))
        roas = _f(row.get("roas"))
        purchases = _f(row.get("purchases"))
        frequency = _f(row.get("frequency"))
        name = str(row.get("name") or "-")
        if spend >= 500 and purchases == 0:
            contributors.append({"name": name, "note": f"₺{spend:,.0f} harcama, satın alma yok"})
        elif spend >= 300 and account_roas > 0 and roas < account_roas * 0.6:
            contributors.append({"name": name, "note": f"ROAS {roas:.2f} (hesap ort. çok altında), ₺{spend:,.0f} harcama"})
        elif frequency >= 4.0 and spend >= 300:
            contributors.append({"name": name, "note": f"Frekans {frequency:.2f} (yorgunluk), ₺{spend:,.0f} harcama"})
        if len(contributors) >= 5:
            break
    return contributors


# Veriden görülemeyen, kullanıcının kontrol etmesi gereken dış faktörler.
EXTERNAL_FACTORS = (
    "Rakip kampanya/teklif değişiklikleri (açık artırmayı etkiler)",
    "Mevsim, tatil veya gündem etkisi",
    "Site / açılış sayfası / fiyat değişikliği (dönüşümü etkiler)",
    "Pixel / Conversions API takip sorunu (dönüşümler eksik raporlanabilir)",
    "Meta algoritma veya öğrenme aşaması dalgalanması",
)
