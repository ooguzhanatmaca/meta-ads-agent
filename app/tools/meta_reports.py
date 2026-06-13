"""Read-only Meta reporting tools for the OpenAI Agents SDK.

Each tool wraps an existing report builder and returns a ready-to-read string.
Meta API errors are caught and returned as a message so the agent can explain
the problem to the user instead of crashing.
"""

from agents import function_tool

from app.meta.account_summary import calculate_summary, format_summary
from app.meta.client import (
    MetaAPIError,
    get_account_insights,
    get_performance_report,
    test_meta_connection,
)
from app.meta.compare_periods import build_period_comparison
from app.meta.executive_summary import build_executive_summary
from app.meta.performance_report import calculate_report_rows, format_report
from app.meta.recommendations import format_recommendations
from app.rules.performance_rules import evaluate_ads


REPORT_TITLES = {
    "campaign": "Kampanya raporu",
    "adset": "Reklam seti raporu",
    "ad": "Reklam raporu",
}


@function_tool
def check_meta_connection() -> str:
    """Meta hesabına bağlantının çalışıp çalışmadığını test eder."""
    try:
        ok = test_meta_connection()
    except MetaAPIError as error:
        return f"Meta bağlantısı kurulamadı: {error}"
    return "Meta bağlantısı başarılı." if ok else "Meta bağlantısı başarısız."


@function_tool
def get_account_summary() -> str:
    """Son 7 günlük hesap performans özetini döndürür.

    Harcama, gösterim, erişim, tıklama, CTR, CPC, CPM, satın alma, CPA ve ROAS
    metriklerini içerir.
    """
    try:
        summary = calculate_summary(get_account_insights("last_7d"))
    except MetaAPIError as error:
        return f"Hesap özeti alınamadı: {error}"
    return format_summary(summary)


@function_tool
def get_performance_report_by_level(level: str) -> str:
    """Belirtilen seviye için son 7 günlük performans raporunu döndürür.

    Args:
        level: "campaign" (kampanya), "adset" (reklam seti) veya "ad" (reklam).
    """
    if level not in REPORT_TITLES:
        return (
            "Geçersiz seviye. Geçerli değerler: 'campaign', 'adset', 'ad'."
        )
    title = REPORT_TITLES[level]
    try:
        entities = get_performance_report(level, "last_7d")
    except MetaAPIError as error:
        return f"{title} alınamadı: {error}"
    return format_report(title, calculate_report_rows(entities))


@function_tool
def get_ad_recommendations() -> str:
    """Son 7 günlük reklam verisine dayalı kural tabanlı önerileri döndürür.

    Kapatılmaya aday, bütçesi artırılabilir ve kreatif yorgunluğu olan
    reklamları, gerekçe ve öncelik bilgisiyle birlikte listeler.
    """
    try:
        entities = get_performance_report("ad", "last_7d")
    except MetaAPIError as error:
        return f"Reklam önerileri oluşturulamadı: {error}"
    ad_rows = calculate_report_rows(entities)
    return format_recommendations(evaluate_ads(ad_rows))


@function_tool
def get_period_comparison() -> str:
    """Varsayılan dönemler için (bugün/dün, son 7 gün/önceki 7 gün) karşılaştırma döndürür."""
    try:
        return build_period_comparison()
    except MetaAPIError as error:
        return f"Dönem karşılaştırması alınamadı: {error}"


@function_tool
def get_executive_summary() -> str:
    """Tüm raporları birleştiren kapsamlı yönetici özetini döndürür.

    Bugünkü performans, dönem karşılaştırmaları, en iyi/en kötü reklamlar ve
    öncelikli aksiyon listesini tek bir özette toplar.
    """
    try:
        return build_executive_summary()
    except MetaAPIError as error:
        return f"Yönetici özeti oluşturulamadı: {error}"
