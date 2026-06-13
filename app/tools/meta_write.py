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
    create_campaign,
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


def _pause_entity(entity_id: str) -> str:
    if not _writes_enabled():
        return DISABLED_MESSAGE
    try:
        set_entity_status(entity_id, "PAUSED")
    except MetaAPIError as error:
        return f"Durdurulamadı: {error}"
    return f"{entity_id} duraklatıldı (harcama durdu)."


def _activate_entity(entity_id: str) -> str:
    if not _writes_enabled():
        return DISABLED_MESSAGE
    try:
        set_entity_status(entity_id, "ACTIVE")
    except MetaAPIError as error:
        return f"Aktifleştirilemedi: {error}"
    return f"{entity_id} aktifleştirildi (yayında — harcama başlayabilir)."


def _update_daily_budget(entity_id: str, daily_budget_try: float) -> str:
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
def pause_entity(entity_id: str) -> str:
    """Bir kampanya/reklam seti/reklamı durdurur (PAUSED). Harcamayı durdurur (güvenli).

    Yalnızca kullanıcının açık onayından sonra çağır.

    Args:
        entity_id: Durdurulacak varlığın ID'si.
    """
    return _pause_entity(entity_id)


@function_tool
def activate_entity(entity_id: str) -> str:
    """Bir kampanya/reklam seti/reklamı yayına alır (ACTIVE).

    DİKKAT: Bu işlem HARCAMA BAŞLATIR. Yalnızca kullanıcının çok net onayıyla çağır.

    Args:
        entity_id: Aktifleştirilecek varlığın ID'si.
    """
    return _activate_entity(entity_id)


@function_tool
def update_daily_budget(entity_id: str, daily_budget_try: float) -> str:
    """Bir kampanya/reklam setinin günlük bütçesini günceller (TL).

    DİKKAT: Harcamayı doğrudan etkiler. Yalnızca kullanıcının açık onayıyla çağır.

    Args:
        entity_id: Bütçesi değişecek varlığın ID'si.
        daily_budget_try: Yeni günlük bütçe (TL cinsinden, ör. 500).
    """
    return _update_daily_budget(entity_id, daily_budget_try)
