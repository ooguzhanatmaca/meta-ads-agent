"""Read-only Meta reporting tools for the OpenAI Agents SDK.

Each tool wraps an existing report builder and returns a ready-to-read string.
Meta API errors are caught and returned as a message so the agent can explain
the problem to the user instead of crashing.
"""

from typing import Any

from agents import function_tool

from app.meta.account_summary import calculate_summary, format_summary
from app.meta.anomaly_report import build_anomaly_report
from app.meta.client import (
    MetaAPIError,
    get_account_insights,
    get_account_insights_breakdown,
    get_custom_audiences,
    get_performance_report,
    test_meta_connection,
)
from app.meta.compare_periods import build_period_comparison
from app.meta.creative_vision import critique_image
from app.meta.diagnosis import build_diagnosis
from app.meta.executive_summary import build_executive_summary
from app.meta.opportunities import build_opportunities
from app.meta.export_excel import export_excel
from app.meta.simulation import build_simulation
from app.meta.weekly_digest import build_weekly_digest
from app.meta.performance_report import calculate_report_rows, format_report
from app.meta.recommendations import format_recommendations
from app.meta.trends import build_trend_report
from app.rules.budget_rules import budget_suggestions
from app.rules.creative_rules import evaluate_creatives
from app.rules.performance_rules import evaluate_ads


REPORT_TITLES = {
    "campaign": "Kampanya raporu",
    "adset": "Reklam seti raporu",
    "ad": "Reklam raporu",
}

# Türkçe/İngilizce kırılım adı -> Meta API breakdowns parametresi.
BREAKDOWN_MAP = {
    "age": "age",
    "yaş": "age",
    "yas": "age",
    "gender": "gender",
    "cinsiyet": "gender",
    "age_gender": "age,gender",
    "yaş_cinsiyet": "age,gender",
    "yas_cinsiyet": "age,gender",
    "placement": "publisher_platform,platform_position",
    "yerleşim": "publisher_platform,platform_position",
    "yerlesim": "publisher_platform,platform_position",
    "platform": "publisher_platform",
    "country": "country",
    "ülke": "country",
    "ulke": "country",
    "region": "region",
    "bölge": "region",
    "bolge": "region",
    "device": "device_platform",
    "cihaz": "device_platform",
}

# Kırılım satırlarında ölçüm dışı (boyut) anahtarları.
BREAKDOWN_KEYS = (
    "age",
    "gender",
    "country",
    "region",
    "publisher_platform",
    "platform_position",
    "device_platform",
    "impression_device",
)


def _cell(value: Any, width: int) -> str:
    text = str(value)
    if len(text) > width:
        text = f"{text[: width - 1]}…"
    return text.ljust(width)


def _table(title: str, headers: tuple, widths: tuple, rows: list[tuple]) -> str:
    if not rows:
        return f"{title}\nKayıt bulunamadı."
    header = " | ".join(_cell(h, w) for h, w in zip(headers, widths))
    separator = "-+-".join("-" * w for w in widths)
    body = [
        " | ".join(_cell(v, w) for v, w in zip(row, widths)) for row in rows
    ]
    return "\n".join((title, header, separator, *body))


@function_tool
def check_meta_connection() -> str:
    """Meta hesabına bağlantının çalışıp çalışmadığını test eder."""
    try:
        ok = test_meta_connection()
    except MetaAPIError as error:
        return f"Meta bağlantısı kurulamadı: {error}"
    return "Meta bağlantısı başarılı." if ok else "Meta bağlantısı başarısız."


@function_tool
def get_account_summary(date_preset: str = "last_7d") -> str:
    """Hesap performans özetini döndürür (harcama, CTR, CPC, CPM, CPA, ROAS vb.).

    Args:
        date_preset: Meta tarih ön ayarı. Örn: today, yesterday, last_7d,
            last_14d, last_30d, last_90d, this_month, last_month, this_year.
    """
    try:
        summary = calculate_summary(get_account_insights(date_preset))
    except MetaAPIError as error:
        return f"Hesap özeti alınamadı: {error}"
    return format_summary(summary)


@function_tool
def get_performance_report_by_level(level: str, date_preset: str = "last_7d") -> str:
    """Belirtilen seviye için performans raporunu döndürür.

    Args:
        level: "campaign" (kampanya), "adset" (reklam seti) veya "ad" (reklam).
        date_preset: Meta tarih ön ayarı (örn. last_7d, last_30d, this_month).
    """
    if level not in REPORT_TITLES:
        return "Geçersiz seviye. Geçerli değerler: 'campaign', 'adset', 'ad'."
    title = REPORT_TITLES[level]
    try:
        entities = get_performance_report(level, date_preset)
    except MetaAPIError as error:
        return f"{title} alınamadı: {error}"
    return format_report(title, calculate_report_rows(entities))


@function_tool
def get_ad_recommendations(date_preset: str = "last_7d") -> str:
    """Reklam verisine dayalı kural tabanlı performans önerilerini döndürür.

    Kapatılmaya aday, bütçesi artırılabilir ve kreatif yorgunluğu olan
    reklamları, gerekçe ve öncelik bilgisiyle listeler.

    Args:
        date_preset: Meta tarih ön ayarı (örn. last_7d, last_30d).
    """
    try:
        entities = get_performance_report("ad", date_preset)
    except MetaAPIError as error:
        return f"Reklam önerileri oluşturulamadı: {error}"
    ad_rows = calculate_report_rows(entities)
    return format_recommendations(evaluate_ads(ad_rows))


@function_tool
def get_creative_analysis(date_preset: str = "last_7d", limit: int = 15) -> str:
    """Reklam kreatiflerinin yorgunluk ve sağlık analizini döndürür.

    Her reklam için sağlık skoru, durum (Sağlıklı/Riskli/Zayıf) ve kreatif
    aksiyonu (yorulan kreatifi değiştir, kazananı koru vb.) üretir.

    Args:
        date_preset: Meta tarih ön ayarı (örn. last_7d, last_30d).
        limit: Listelenecek maksimum reklam sayısı.
    """
    try:
        entities = get_performance_report("ad", date_preset)
    except MetaAPIError as error:
        return f"Kreatif analizi oluşturulamadı: {error}"
    results = evaluate_creatives(calculate_report_rows(entities))[: max(1, limit)]
    rows = [
        (
            item["name"],
            f"{item['spend']:.2f}",
            f"{item['roas']:.2f}",
            f"{item['frequency']:.2f}",
            f"{item['health_score']}/100",
            item["health_status"],
            item["creative_label"],
            item["creative_recommendation"],
        )
        for item in results
    ]
    return _table(
        "Kreatif yorgunluk ve sağlık analizi",
        ("Reklam", "Harcama", "ROAS", "Frekans", "Sağlık", "Durum", "Etiket", "Öneri"),
        (22, 10, 7, 8, 8, 9, 22, 40),
        rows,
    )


@function_tool
def get_budget_suggestions(level: str = "campaign", date_preset: str = "last_7d") -> str:
    """Sayısal bütçe önerileri döndürür (önerilen günlük bütçe dahil).

    Yüksek ROAS + düşük frekanslı varlıklara artış, verimsizlere azaltma/durdurma
    önerir. Önerilen günlük bütçe, dönemdeki ortalama günlük harcamadan türetilir.
    Bu yalnızca tavsiyedir; bütçeyi değiştirmez.

    Args:
        level: "campaign", "adset" veya "ad".
        date_preset: Meta tarih ön ayarı (örn. last_7d, last_30d).
    """
    if level not in REPORT_TITLES:
        return "Geçersiz seviye. Geçerli değerler: 'campaign', 'adset', 'ad'."
    window = {"last_7d": 7, "last_14d": 14, "last_30d": 30, "last_90d": 90}.get(
        date_preset, 7
    )
    try:
        entities = get_performance_report(level, date_preset)
    except MetaAPIError as error:
        return f"Bütçe önerileri oluşturulamadı: {error}"
    suggestions = budget_suggestions(calculate_report_rows(entities), window)
    rows = [
        (
            s["name"],
            f"{s['spend']:.2f}",
            f"{s['roas']:.2f}",
            f"{s['frequency']:.2f}",
            s["action"],
            f"%{s['change_pct']:+d}",
            f"{s['suggested_daily']:.2f}",
            s["reason"],
        )
        for s in suggestions
    ]
    return _table(
        f"Bütçe önerileri ({level})",
        ("Varlık", "Harcama", "ROAS", "Frekans", "Aksiyon", "Değişim", "Öneri Günlük", "Gerekçe"),
        (22, 10, 7, 8, 22, 8, 13, 42),
        rows,
    )


@function_tool
def get_breakdown_report(dimension: str, date_preset: str = "last_7d") -> str:
    """Hesap performansını bir boyuta göre kırarak döndürür.

    Args:
        dimension: Kırılım boyutu. Örn: "age" (yaş), "gender" (cinsiyet),
            "age_gender" (yaş+cinsiyet), "placement" (yerleşim), "platform",
            "country" (ülke), "region" (bölge), "device" (cihaz).
        date_preset: Meta tarih ön ayarı (örn. last_7d, last_30d).
    """
    breakdowns = BREAKDOWN_MAP.get(dimension.strip().lower())
    if breakdowns is None:
        return (
            "Geçersiz boyut. Örnekler: age, gender, age_gender, placement, "
            "platform, country, region, device."
        )
    try:
        data = get_account_insights_breakdown(breakdowns, date_preset)
    except MetaAPIError as error:
        return f"Kırılım raporu alınamadı: {error}"

    rows = []
    for item in data:
        label = " / ".join(
            str(item[k]) for k in BREAKDOWN_KEYS if item.get(k) is not None
        )
        m = calculate_summary(item)
        rows.append(
            (
                label or "-",
                f"{m['spend']:.2f}",
                f"{m['impressions']:.0f}",
                f"{m['clicks']:.0f}",
                f"%{m['ctr']:.2f}",
                f"{m['purchases']:.0f}",
                f"{m['roas']:.2f}",
                f"{m['cpa']:.2f}",
            )
        )
    rows.sort(key=lambda r: float(r[1]), reverse=True)
    return _table(
        f"Kırılım raporu: {dimension}",
        ("Kırılım", "Harcama", "Gösterim", "Tıklama", "CTR", "Satın Alma", "ROAS", "CPA"),
        (26, 11, 11, 10, 9, 11, 9, 9),
        rows,
    )


def _find_ad(rows: list[dict[str, Any]], ad_name: str) -> dict[str, Any] | None:
    """Find an ad row by (case-insensitive) name match; prefer exact, else contains."""
    query = ad_name.strip().lower()
    for row in rows:
        if str(row.get("name", "")).lower() == query:
            return row
    for row in rows:
        if query in str(row.get("name", "")).lower():
            return row
    return None


@function_tool
def get_creative_brief(date_preset: str = "last_7d", limit: int = 5) -> str:
    """Kreatif aksiyonu gereken reklamlar için metrik + kural tabanlı kreatif brief döndürür.

    Çıktıdaki hook/açı/format/kanıt/CTA önerilerine dayanarak yeni reklam metni
    (başlık + birincil metin) varyasyonları yazabilirsin.

    Args:
        date_preset: Meta tarih ön ayarı (örn. last_7d, last_30d).
        limit: Brief üretilecek maksimum reklam sayısı.
    """
    try:
        entities = get_performance_report("ad", date_preset)
    except MetaAPIError as error:
        return f"Kreatif brief oluşturulamadı: {error}"
    results = evaluate_creatives(calculate_report_rows(entities))[: max(1, limit)]
    blocks = []
    for item in results:
        brief = item.get("creative_brief", {})
        blocks.append(
            "\n".join(
                (
                    f"Reklam: {item['name']}",
                    f"  Tür: {item.get('creative_type', '-')} | ROAS: {item['roas']:.2f} | "
                    f"CTR: %{item['ctr']:.2f} | Frekans: {item['frequency']:.2f}",
                    f"  Durum: {item['creative_label']} — {item['creative_recommendation']}",
                    f"  Hook: {brief.get('hook', '-')}",
                    f"  Açı: {brief.get('angle', '-')}",
                    f"  Format: {brief.get('format', '-')}",
                    f"  Kanıt: {brief.get('proof', '-')}",
                    f"  CTA: {brief.get('cta', '-')}",
                )
            )
        )
    if not blocks:
        return "Kreatif brief için reklam bulunamadı."
    return "Kreatif brief (yeni metin yazmak için kullan):\n\n" + "\n\n".join(blocks)


@function_tool
def analyze_ad_creative(ad_name: str, date_preset: str = "last_7d") -> str:
    """Bir reklamın görseline bakıp kreatif geri bildirim verir (Gemini görsel analizi).

    Args:
        ad_name: Reklamın adı (kısmi ad da kabul edilir).
        date_preset: Meta tarih ön ayarı (örn. last_7d, last_30d).
    """
    try:
        rows = calculate_report_rows(get_performance_report("ad", date_preset))
    except MetaAPIError as error:
        return f"Reklam verisi alınamadı: {error}"

    match = _find_ad(rows, ad_name)
    if match is None:
        return f"'{ad_name}' adlı reklam bulunamadı."
    image_url = match.get("thumbnail_url")
    if not image_url:
        return (
            f"'{match['name']}' için görsel bulunamadı "
            "(video önizlemesi olmayabilir)."
        )
    try:
        critique = critique_image(image_url)
    except Exception as error:  # noqa: BLE001
        return f"Görsel analizi yapılamadı: {error}"
    return f"Reklam: {match['name']}\n\n{critique}"


@function_tool
def list_custom_audiences() -> str:
    """Hesaptaki mevcut özel/benzer (lookalike) kitleleri listeler.

    Lookalike oluşturmak için kaynak kitle seçmek üzere kullan; kullanıcıya
    hangi kitleyi baz alacağını sorabilirsin.
    """
    try:
        audiences = get_custom_audiences()
    except MetaAPIError as error:
        return f"Kitleler alınamadı: {error}"
    if not audiences:
        return "Hesapta tanımlı özel kitle bulunamadı."
    rows = [
        (
            str(a.get("id", "-")),
            str(a.get("name", "-")),
            str(a.get("subtype", "-")),
            str(a.get("approximate_count_lower_bound", "-")),
        )
        for a in audiences
    ]
    return _table(
        "Mevcut özel kitleler",
        ("ID", "Ad", "Tür", "~Boyut"),
        (20, 34, 14, 12),
        rows,
    )


@function_tool
def find_opportunities() -> str:
    """Veri odaklı büyüme fırsatları üretir (agent'ın stratejik fikirleri).

    Yetersiz hedeflenen kazanan segmentler, verimli yerleşimler, bütçe yeniden
    dağıtımı, ölçeklemeye uygun setler ve denenmemiş kitle fikirlerini bulur.
    "Ne yapabilirim / nasıl büyütürüm / yeni ne deneyeyim / fikir/öneri ver"
    sorularında kullan. Klonlamanın ötesinde yeni stratejiler önerir.
    """
    try:
        return build_opportunities()
    except MetaAPIError as error:
        return f"Fırsat analizi yapılamadı: {error}"


@function_tool
def diagnose_change() -> str:
    """Kök neden analizi: bir metrik (ROAS, CPA vb.) neden değişti sorusunu yanıtlar.

    Son 7 gün ile önceki 7 günü karşılaştırıp olası nedenleri kanıtlarıyla sıralar,
    ortalamayı aşağı çeken varlıkları listeler ve veriden görülemeyen (kullanıcının
    kontrol etmesi gereken) dış faktörleri belirtir. "Neden düştü/arttı", "sebebi ne"
    gibi sorularda kullan.
    """
    try:
        return build_diagnosis()
    except MetaAPIError as error:
        return f"Kök neden analizi yapılamadı: {error}"


@function_tool
def get_anomaly_alerts() -> str:
    """Hesapta dikkat gerektiren anomalileri (uyarıları) tespit eder.

    CPA artışı, ROAS düşüşü, harcama temposu, satışsız harcama ve kreatif
    yorgunluğu gibi sorunları kontrol eder; sorun yoksa bunu açıkça belirtir.
    """
    try:
        return build_anomaly_report()
    except MetaAPIError as error:
        return f"Uyarılar oluşturulamadı: {error}"


@function_tool
def get_trend(metric: str = "özet", days: int = 14) -> str:
    """Bir metriğin günlük geçmiş trendini mini grafik (sparkline) ile döndürür.

    Yavaş bozulmaları/iyileşmeleri yakalar (ör. "ROAS son 2 haftada düşüyor mu").

    Args:
        metric: "roas", "cpa", "ctr", "cpc", "harcama", "satın alma" veya genel
            bakış için "özet".
        days: Geriye dönük gün sayısı (örn. 7, 14, 30).
    """
    try:
        return build_trend_report(metric, days)
    except MetaAPIError as error:
        return f"Trend alınamadı: {error}"


@function_tool
def get_period_comparison() -> str:
    """Varsayılan dönemler için (bugün/dün, son 7 gün/önceki 7 gün) karşılaştırma döndürür."""
    try:
        return build_period_comparison()
    except MetaAPIError as error:
        return f"Dönem karşılaştırması alınamadı: {error}"


@function_tool
def simulate_change(
    target_name: str,
    change_pct: float = 0.0,
    pause: bool = False,
    level: str = "campaign",
    date_preset: str = "last_7d",
) -> str:
    """"Ne olur?" senaryosu: bir varlığın bütçesini değiştirmenin/kapatmanın
    hesap geneline tahmini etkisini (öncesi→sonrası) hesaplar. Bu bir tahmindir,
    hiçbir şeyi değiştirmez.

    Args:
        target_name: Etkilenecek kampanya/reklam seti/reklam adı (kısmi ad olur).
        change_pct: Bütçe değişimi yüzdesi (ör. +30 artış, -20 azalış). pause=True ise yok sayılır.
        pause: True ise varlığı kapatma senaryosu simüle edilir.
        level: "campaign", "adset" veya "ad".
        date_preset: Meta tarih ön ayarı (örn. last_7d, last_30d).
    """
    if level not in REPORT_TITLES:
        return "Geçersiz seviye. Geçerli değerler: 'campaign', 'adset', 'ad'."
    try:
        return build_simulation(target_name, change_pct, pause, level, date_preset)
    except MetaAPIError as error:
        return f"Simülasyon yapılamadı: {error}"


@function_tool
def get_weekly_digest() -> str:
    """Akıllı haftalık özet: bu hafta vs geçen hafta + en iyi/kötü reklamlar + uyarılar."""
    try:
        return build_weekly_digest()
    except MetaAPIError as error:
        return f"Haftalık özet oluşturulamadı: {error}"


@function_tool
def export_excel_report() -> str:
    """Kapsamlı raporu Excel (.xlsx) dosyası olarak kaydeder ve dosya yolunu döndürür.

    Kullanıcı 'Excel raporu çıkar / dosya olarak ver' dediğinde kullan.
    """
    try:
        path = export_excel()
    except MetaAPIError as error:
        return f"Excel raporu oluşturulamadı: {error}"
    return f"Excel raporu kaydedildi: {path}"


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
