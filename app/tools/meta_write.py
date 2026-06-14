"""Guarded write (operator) tools for the Meta ad account.

SAFETY:
- All writes are disabled unless ENABLE_WRITE_ACTIONS is true in the environment.
- New campaigns are created PAUSED (no spend until the user activates them).
- The agent must get explicit user confirmation before calling any of these.

The logic lives in plain ``_impl`` helpers (testable); the @function_tool
wrappers are thin delegators that expose the schema to the agent.
"""

import os

from agents import function_tool

from app.meta.client import (
    MetaAPIError,
    clone_ad_set,
    create_ad,
    create_ad_set,
    create_campaign,
    create_lookalike_audience,
    get_entity,
    set_daily_budget,
    set_entity_status,
)


VALID_OBJECTIVES = {
    "OUTCOME_TRAFFIC",
    "OUTCOME_SALES",
    "OUTCOME_LEADS",
    "OUTCOME_ENGAGEMENT",
    "OUTCOME_AWARENESS",
    "OUTCOME_APP_PROMOTION",
}

DISABLED_MESSAGE = (
    "Yazma işlemleri güvenlik için KAPALI. Etkinleştirmek için .env içinde "
    "ENABLE_WRITE_ACTIONS=true yapıp agent'ı yeniden başlatın. "
    "(Meta token'ının ads_management iznine de sahip olması gerekir.)"
)


def _writes_enabled() -> bool:
    return os.getenv("ENABLE_WRITE_ACTIONS", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "evet",
    }


PREVIEW_PREFIX = "ÖNİZLEME (henüz uygulanmadı):"


def _entity_snapshot(entity_id: str) -> dict[str, object]:
    """Read an entity's current name/status/daily budget for a change preview.

    Returns an empty dict on any read failure — the preview still shows the
    intended new value, just without the current one.
    """
    try:
        data = get_entity(entity_id, "name,status,daily_budget")
    except MetaAPIError:
        return {}
    snapshot: dict[str, object] = {
        "name": data.get("name"),
        "status": data.get("status"),
    }
    if data.get("daily_budget") is not None:
        try:
            snapshot["daily_budget_try"] = int(data["daily_budget"]) / 100
        except (TypeError, ValueError):
            pass
    return snapshot


def _create_paused_campaign(name: str, objective: str = "OUTCOME_TRAFFIC") -> str:
    if not _writes_enabled():
        return DISABLED_MESSAGE
    if objective not in VALID_OBJECTIVES:
        return f"Geçersiz hedef. Geçerli değerler: {', '.join(sorted(VALID_OBJECTIVES))}."
    try:
        result = create_campaign(name, objective, "PAUSED")
    except MetaAPIError as error:
        return f"Kampanya oluşturulamadı: {error}"
    return (
        f"Kampanya DURAKLATILMIŞ olarak oluşturuldu (id: {result.get('id')}). "
        "Harcama başlamaz; Ads Manager'dan kontrol edip yayına alabilirsiniz."
    )


VALID_OPTIMIZATION_GOALS = {
    "LINK_CLICKS",
    "LANDING_PAGE_VIEWS",
    "OFFSITE_CONVERSIONS",
    "REACH",
    "IMPRESSIONS",
    "THRUPLAY",
}


def _create_ad_set(
    campaign_id: str,
    name: str,
    daily_budget_try: float,
    optimization_goal: str = "LINK_CLICKS",
    country: str = "TR",
    age_min: int = 18,
    age_max: int = 65,
    pixel_id: str = "",
    custom_event_type: str = "",
) -> str:
    if not _writes_enabled():
        return DISABLED_MESSAGE
    if optimization_goal not in VALID_OPTIMIZATION_GOALS:
        return f"Geçersiz optimizasyon hedefi. Geçerli: {', '.join(sorted(VALID_OPTIMIZATION_GOALS))}."
    minor = int(round(float(daily_budget_try) * 100))
    try:
        result = create_ad_set(
            campaign_id,
            name,
            minor,
            optimization_goal=optimization_goal,
            countries=(country,),
            age_min=age_min,
            age_max=age_max,
            pixel_id=pixel_id or None,
            custom_event_type=custom_event_type or None,
        )
    except MetaAPIError as error:
        return f"Reklam seti oluşturulamadı: {error}"
    return (
        f"Reklam seti DURAKLATILMIŞ olarak oluşturuldu (id: {result.get('id')}). "
        f"Günlük bütçe {daily_budget_try:.2f} TL, hedef ülke {country}, yaş {age_min}-{age_max}."
    )


def _create_lookalike_audience(
    source_audience_id: str,
    name: str,
    country: str = "TR",
    ratio: float = 0.01,
) -> str:
    if not _writes_enabled():
        return DISABLED_MESSAGE
    if not 0.01 <= ratio <= 0.20:
        return "Oran (ratio) 0.01 ile 0.20 arasında olmalı (%1-%20)."
    try:
        result = create_lookalike_audience(source_audience_id, name, country, ratio)
    except MetaAPIError as error:
        return f"Benzer kitle oluşturulamadı: {error}"
    return (
        f"Benzer (lookalike) kitle oluşturuldu (id: {result.get('id')}); "
        f"kaynak {source_audience_id}, {country} %{ratio * 100:.0f}. "
        "Kitle hazır olunca reklam setlerinde hedefleyebilirsiniz."
    )


def _clone_ad_set(
    source_adset_id: str,
    new_name: str,
    budget_multiplier: float = 1.0,
    new_campaign_id: str = "",
) -> str:
    if not _writes_enabled():
        return DISABLED_MESSAGE
    try:
        result = clone_ad_set(
            source_adset_id, new_name, budget_multiplier, new_campaign_id or None
        )
    except MetaAPIError as error:
        return f"Reklam seti klonlanamadı: {error}"
    note = f" (bütçe x{budget_multiplier:g})" if budget_multiplier != 1.0 else ""
    return (
        f"Kazanan setin ayarları (hedefleme, bütçe, optimizasyon) kopyalanarak "
        f"yeni reklam seti DURAKLATILMIŞ oluşturuldu (id: {result.get('id')}){note}. "
        "Ads Manager'dan kontrol edip yayına alabilirsiniz."
    )


def _create_ad(adset_id: str, name: str, creative_id: str) -> str:
    if not _writes_enabled():
        return DISABLED_MESSAGE
    try:
        result = create_ad(adset_id, name, creative_id)
    except MetaAPIError as error:
        return f"Reklam oluşturulamadı: {error}"
    return (
        f"Reklam DURAKLATILMIŞ olarak oluşturuldu (id: {result.get('id')}). "
        "Ads Manager'dan kontrol edip yayına alabilirsiniz."
    )


def _pause_entity(entity_id: str, dry_run: bool = False) -> str:
    if dry_run:
        snap = _entity_snapshot(entity_id)
        label = f"'{snap['name']}' ({entity_id})" if snap.get("name") else entity_id
        return (
            f"{PREVIEW_PREFIX} {label} DURAKLATILACAK; harcaması duracak. "
            "Onaylarsanız uygularım."
        )
    if not _writes_enabled():
        return DISABLED_MESSAGE
    try:
        set_entity_status(entity_id, "PAUSED")
    except MetaAPIError as error:
        return f"Durdurulamadı: {error}"
    return f"{entity_id} duraklatıldı (harcama durdu)."


def _activate_entity(entity_id: str, dry_run: bool = False) -> str:
    if dry_run:
        snap = _entity_snapshot(entity_id)
        label = f"'{snap['name']}' ({entity_id})" if snap.get("name") else entity_id
        budget = snap.get("daily_budget_try")
        spend_note = (
            f"günlük yaklaşık {budget:.2f} TL harcama başlayabilir"
            if isinstance(budget, (int, float))
            else "harcama başlayabilir"
        )
        return (
            f"{PREVIEW_PREFIX} {label} YAYINA ALINACAK; {spend_note}. "
            "Onaylarsanız uygularım."
        )
    if not _writes_enabled():
        return DISABLED_MESSAGE
    try:
        set_entity_status(entity_id, "ACTIVE")
    except MetaAPIError as error:
        return f"Aktifleştirilemedi: {error}"
    return f"{entity_id} aktifleştirildi (yayında — harcama başlayabilir)."


def _update_daily_budget(
    entity_id: str, daily_budget_try: float, dry_run: bool = False
) -> str:
    if dry_run:
        snap = _entity_snapshot(entity_id)
        label = f"'{snap['name']}' ({entity_id})" if snap.get("name") else entity_id
        current = snap.get("daily_budget_try")
        if isinstance(current, (int, float)) and current > 0:
            pct = (daily_budget_try - current) / current * 100
            change = (
                f"{current:.2f} TL → {daily_budget_try:.2f} TL "
                f"(%{pct:+.0f})"
            )
        else:
            change = f"yeni günlük bütçe {daily_budget_try:.2f} TL"
        return (
            f"{PREVIEW_PREFIX} {label} günlük bütçesi {change} olarak değişecek. "
            "Onaylarsanız uygularım."
        )
    if not _writes_enabled():
        return DISABLED_MESSAGE
    minor = int(round(float(daily_budget_try) * 100))  # TL -> kuruş
    try:
        set_daily_budget(entity_id, minor)
    except MetaAPIError as error:
        return f"Bütçe güncellenemedi: {error}"
    return f"{entity_id} günlük bütçesi {daily_budget_try:.2f} TL olarak güncellendi."


@function_tool
def create_paused_campaign(name: str, objective: str = "OUTCOME_TRAFFIC") -> str:
    """Yeni bir kampanyayı DURAKLATILMIŞ (paused) olarak oluşturur — harcama başlatmaz.

    Yalnızca kullanıcının açık onayından sonra çağır. Oluşturduktan sonra
    kullanıcının Ads Manager'dan kontrol edip yayına almasını söyle.

    Args:
        name: Kampanya adı.
        objective: Hedef. Geçerli: OUTCOME_TRAFFIC, OUTCOME_SALES, OUTCOME_LEADS,
            OUTCOME_ENGAGEMENT, OUTCOME_AWARENESS, OUTCOME_APP_PROMOTION.
    """
    return _create_paused_campaign(name, objective)


@function_tool
def create_ad_set_tool(
    campaign_id: str,
    name: str,
    daily_budget_try: float,
    optimization_goal: str = "LINK_CLICKS",
    country: str = "TR",
    age_min: int = 18,
    age_max: int = 65,
    pixel_id: str = "",
    custom_event_type: str = "",
) -> str:
    """Bir kampanya altında DURAKLATILMIŞ reklam seti oluşturur (temel hedefleme).

    Yalnızca kullanıcının açık onayından sonra çağır. Dönüşüm optimizasyonu
    (OFFSITE_CONVERSIONS) için pixel_id gerekir.

    Args:
        campaign_id: Üst kampanyanın ID'si (önce create_paused_campaign ile alın).
        name: Reklam seti adı.
        daily_budget_try: Günlük bütçe (TL).
        optimization_goal: LINK_CLICKS, LANDING_PAGE_VIEWS, OFFSITE_CONVERSIONS,
            REACH, IMPRESSIONS veya THRUPLAY.
        country: Hedef ülke kodu (ör. TR).
        age_min: Minimum yaş.
        age_max: Maksimum yaş.
        pixel_id: Dönüşüm optimizasyonu için pixel ID (opsiyonel).
        custom_event_type: pixel ile birlikte olay türü (ör. PURCHASE).
    """
    return _create_ad_set(
        campaign_id, name, daily_budget_try, optimization_goal, country,
        age_min, age_max, pixel_id, custom_event_type,
    )


@function_tool
def create_lookalike_audience_tool(
    source_audience_id: str,
    name: str,
    country: str = "TR",
    ratio: float = 0.01,
) -> str:
    """Mevcut bir kaynak kitleden benzer (lookalike) kitle oluşturur.

    Önce list_custom_audiences ile kaynak kitlenin id'sini belirle. Kitle sadece
    tanımdır (harcama yapmaz) ama yine de kullanıcının açık onayıyla çağır.

    Args:
        source_audience_id: Baz alınacak kaynak kitlenin ID'si.
        name: Yeni benzer kitlenin adı.
        country: Hedef ülke kodu (ör. TR).
        ratio: Benzerlik oranı 0.01-0.20 (%1-%20; düşük = daha benzer/dar).
    """
    return _create_lookalike_audience(source_audience_id, name, country, ratio)


@function_tool
def clone_ad_set_tool(
    source_adset_id: str,
    new_name: str,
    budget_multiplier: float = 1.0,
    new_campaign_id: str = "",
) -> str:
    """Kazanan bir reklam setini baz alıp ayarlarını kopyalayarak yeni set oluşturur.

    Kaynak setin GERÇEK hedeflemesini (ilgi alanları, kitleler, yerleşimler),
    bütçesini, optimizasyon hedefini ve teklif stratejisini kopyalar; yeni set
    DURAKLATILMIŞ oluşturulur. Önce reklam seti raporundan en iyi (en yüksek ROAS)
    setin id'sini belirle, sonra bunu çağır. Yalnızca kullanıcının açık onayıyla.

    Args:
        source_adset_id: Baz alınacak (kazanan) reklam setinin ID'si.
        new_name: Yeni setin adı.
        budget_multiplier: Bütçe çarpanı (ör. ölçeklemek için 1.5 = %50 fazla).
        new_campaign_id: Yeni set farklı bir kampanyaya bağlanacaksa ID (opsiyonel;
            boşsa kaynak setin kampanyası kullanılır).
    """
    return _clone_ad_set(source_adset_id, new_name, budget_multiplier, new_campaign_id)


@function_tool
def create_ad_tool(adset_id: str, name: str, creative_id: str) -> str:
    """Bir reklam seti içinde, MEVCUT bir kreatifi kullanarak DURAKLATILMIŞ reklam oluşturur.

    Yalnızca kullanıcının açık onayından sonra çağır. creative_id'yi mevcut bir
    reklamdan alabilirsiniz (reklam raporundaki creative_id alanı).

    Args:
        adset_id: Reklamın ekleneceği reklam setinin ID'si.
        name: Reklam adı.
        creative_id: Kullanılacak mevcut kreatifin ID'si.
    """
    return _create_ad(adset_id, name, creative_id)


@function_tool
def pause_entity(entity_id: str, dry_run: bool = False) -> str:
    """Bir kampanya/reklam seti/reklamı durdurur (PAUSED). Harcamayı durdurur (güvenli).

    Yalnızca kullanıcının açık onayından sonra çağır.

    Args:
        entity_id: Durdurulacak varlığın ID'si.
        dry_run: True ise hiçbir şeyi değiştirmez; yalnızca ne olacağını önizler.
    """
    return _pause_entity(entity_id, dry_run)


@function_tool
def activate_entity(entity_id: str, dry_run: bool = False) -> str:
    """Bir kampanya/reklam seti/reklamı yayına alır (ACTIVE).

    DİKKAT: Bu işlem HARCAMA BAŞLATIR. ÖNCE dry_run=True ile önizleme yap, hangi
    varlığın yayına alınacağını ve harcama etkisini kullanıcıya göster, açık onay
    al; SONRA dry_run=False ile uygula.

    Args:
        entity_id: Aktifleştirilecek varlığın ID'si.
        dry_run: True ise hiçbir şeyi değiştirmez; yalnızca ne olacağını önizler.
    """
    return _activate_entity(entity_id, dry_run)


@function_tool
def update_daily_budget(
    entity_id: str, daily_budget_try: float, dry_run: bool = False
) -> str:
    """Bir kampanya/reklam setinin günlük bütçesini günceller (TL).

    DİKKAT: Harcamayı doğrudan etkiler. ÖNCE dry_run=True ile önizleme yap; mevcut
    bütçe → yeni bütçe değişimini kullanıcıya göster, açık onay al; SONRA
    dry_run=False ile uygula.

    Args:
        entity_id: Bütçesi değişecek varlığın ID'si.
        daily_budget_try: Yeni günlük bütçe (TL cinsinden, ör. 500).
        dry_run: True ise hiçbir şeyi değiştirmez; mevcut→yeni bütçeyi önizler.
    """
    return _update_daily_budget(entity_id, daily_budget_try, dry_run)
