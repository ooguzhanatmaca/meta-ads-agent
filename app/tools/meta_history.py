"""Agent tools for persistent memory: snapshots + recommendation tracking.

These let the agent remember the advice it gives and review later whether it was
followed and how the metric moved — turning it into an ongoing advisor.

The data logic lives in :mod:`app.meta.history` (pure, testable). These thin
``@function_tool`` wrappers fetch current Meta data when needed and format the
result for the agent.
"""

from __future__ import annotations

from typing import Any

from agents import function_tool

from app.meta import history
from app.meta.account_summary import calculate_summary
from app.meta.client import (
    MetaAPIError,
    get_account_insights,
    get_performance_report,
)
from app.meta.performance_report import calculate_report_rows


_ENTITY_LEVELS = {"campaign", "adset", "ad"}


def _account_id() -> str:
    """Best-effort configured account id (for namespacing); '-' if unavailable."""
    try:
        from app.meta.client import MetaClient

        return MetaClient.from_env().ad_account_id
    except Exception:  # noqa: BLE001 — namespacing is best-effort, never fatal
        return "-"


def _current_rows(level: str, date_preset: str = "last_7d") -> list[dict[str, Any]]:
    """Fetch current metrics for a level as uniform rows (id/name/status/metrics)."""
    if level == "account":
        summary = calculate_summary(get_account_insights(date_preset))
        reach = summary.get("reach") or 0
        summary["frequency"] = summary["impressions"] / reach if reach else 0.0
        return [{"id": "account", "name": "Hesap", "status": "-", **summary}]
    if level in _ENTITY_LEVELS:
        return calculate_report_rows(get_performance_report(level, date_preset))
    raise ValueError(f"Geçersiz seviye: {level}. Geçerli: account, campaign, adset, ad.")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def _save_snapshot(level: str = "account", date_preset: str = "last_7d") -> str:
    try:
        rows = _current_rows(level, date_preset)
    except MetaAPIError as error:
        return f"Snapshot alınamadı: {error}"
    except ValueError as error:
        return str(error)
    conn = history.connect()
    try:
        count = history.save_snapshot(conn, level, rows, account_id=_account_id())
    finally:
        conn.close()
    return (
        f"{count} kayıt için '{level}' metrik anlık görüntüsü kaydedildi (bugün). "
        "Zamanla biriken bu geçmişi metrik trend takibinde kullanacağım."
    )


def _log_recommendation(
    level: str,
    entity_id: str,
    entity_name: str,
    action: str,
    reason: str = "",
    metric_name: str = "",
    metric_value: float = 0.0,
) -> str:
    conn = history.connect()
    try:
        rec_id = history.record_recommendation(
            conn,
            level=level,
            entity_id=entity_id,
            entity_name=entity_name,
            action=action,
            reason=reason,
            metric_name=metric_name,
            metric_value=metric_value if metric_name else None,
            account_id=_account_id(),
        )
    finally:
        conn.close()
    metric_part = f" ({metric_name.upper()}={metric_value:.2f})" if metric_name else ""
    return (
        f"Öneri #{rec_id} kaydedildi: '{entity_name}' için {action}{metric_part}. "
        "Sonraki incelemede sonucunu (uygulandı mı, metrik nasıl değişti) takip edeceğim."
    )


def _review_recommendations(date_preset: str = "last_7d") -> str:
    account_id = _account_id()
    conn = history.connect()
    try:
        open_recs = history.list_recommendations(conn, status="open", account_id=account_id)
        if not open_recs:
            return (
                "Takip edilen açık öneri yok. Bir öneri verdiğinde log_recommendation "
                "ile kaydet ki sonradan sonucunu izleyebileyim."
            )

        # Fetch current metrics once per level that has open recommendations.
        levels = {rec["level"] for rec in open_recs}
        current: dict[str, dict[str, dict[str, Any]]] = {}
        for level in levels:
            try:
                rows = _current_rows(level, date_preset)
                current[level] = {str(row["id"]): row for row in rows}
            except (MetaAPIError, ValueError):
                current[level] = {}

        lines = ["Geçmiş önerilerin sonucu:", ""]
        for rec in open_recs:
            row = current.get(rec["level"], {}).get(str(rec["entity_id"]))
            head = (
                f"#{rec['id']} [{rec['created_on']}] '{rec['entity_name']}' — "
                f"{rec['action']}"
            )
            if rec["reason"]:
                head += f" (gerekçe: {rec['reason']})"
            lines.append(head)

            if row is None:
                lines.append(
                    "   Durum: bu varlık güncel raporda bulunamadı "
                    "(kapatılmış/silinmiş olabilir)."
                )
                lines.append("")
                continue

            status_note = f"   Güncel durum: {row.get('status', '-')}"
            metric_name = rec["metric_name"]
            if metric_name and metric_name in history.TRACKED_METRICS:
                outcome = history.evaluate_outcome(
                    metric_name, rec["metric_value"], float(row.get(metric_name) or 0.0)
                )
                status_note += f" · {outcome['note']}"
            lines.append(status_note)
            lines.append("")

        lines.append(
            "Bir öneri uygulandıysa mark_recommendation ile 'followed', "
            "geçersizse 'dismissed' olarak işaretleyebilirim."
        )
        return "\n".join(lines)
    finally:
        conn.close()


def _show_metric_history(
    level: str,
    entity: str,
    metric: str = "roas",
    days: int = 30,
) -> str:
    account_id = _account_id()
    conn = history.connect()
    try:
        entity_id = entity
        entity_name = entity
        if level != "account":
            resolved = history.find_entity_id(conn, level, entity, account_id=account_id)
            if resolved is None:
                return (
                    f"'{entity}' için kayıtlı geçmiş bulunamadı. Geçmiş ancak "
                    "snapshot'lar biriktikçe oluşur (günlük rapor bunu otomatik yapar)."
                )
            entity_id = resolved["entity_id"]
            entity_name = resolved["entity_name"]

        try:
            series = history.metric_history(
                conn, level, entity_id, metric, account_id=account_id, limit=days
            )
        except ValueError as error:
            return str(error)
    finally:
        conn.close()

    if not series:
        return (
            f"'{entity_name}' için {metric.upper()} geçmişi henüz yok. "
            "Snapshot biriktikçe burada trend görünecek."
        )
    if len(series) == 1:
        only = series[0]
        return (
            f"'{entity_name}' {metric.upper()} geçmişinde tek gün var "
            f"({only['taken_on']}: {only['value']:.2f}). Trend için daha fazla gün gerekli."
        )

    first, last = series[0], series[-1]
    outcome = history.evaluate_outcome(metric, first["value"], last["value"])
    lines = [f"'{entity_name}' — {metric.upper()} geçmişi ({len(series)} gün):"]
    for point in series:
        lines.append(f"   {point['taken_on']}: {point['value']:.2f}")
    lines.append("")
    lines.append(
        f"{first['taken_on']} → {last['taken_on']}: {outcome['note']}"
    )
    return "\n".join(lines)


def _mark_recommendation(rec_id: int, status: str, note: str = "") -> str:
    conn = history.connect()
    try:
        try:
            ok = history.update_recommendation(
                conn, rec_id, status=status, outcome_note=note or None
            )
        except ValueError as error:
            return str(error)
    finally:
        conn.close()
    if not ok:
        return f"#{rec_id} numaralı öneri bulunamadı."
    return f"Öneri #{rec_id} '{status}' olarak işaretlendi."


@function_tool
def save_metrics_snapshot(level: str = "account", date_preset: str = "last_7d") -> str:
    """Güncel metrikleri kalıcı geçmişe (snapshot) kaydeder; trend takibini besler.

    Günlük rapor bunu otomatik yapar; kullanıcı 'şu anki durumu kaydet' derse veya
    elle bir karşılaştırma noktası bırakmak isterse de çağrılabilir.

    Args:
        level: account, campaign, adset veya ad.
        date_preset: Hangi dönemin metrikleri kaydedilsin (varsayılan last_7d).
    """
    return _save_snapshot(level, date_preset)


@function_tool
def log_recommendation(
    level: str,
    entity_id: str,
    entity_name: str,
    action: str,
    reason: str = "",
    metric_name: str = "",
    metric_value: float = 0.0,
) -> str:
    """Verdiğin bir öneriyi kalıcı günlüğe kaydeder; sonradan sonucu izlenebilsin.

    Kullanıcıya somut bir aksiyon önerdikten sonra (ör. bir reklamı kapatma, bütçe
    artırma) bunu çağır. Daha sonra review_recommendations ile metrik gerçekten
    iyileşti mi diye bakılır. metric_name + metric_value vermek, sonradan
    iyileşme/kötüleşme ölçümünü mümkün kılar.

    Args:
        level: account, campaign, adset veya ad.
        entity_id: Önerinin ilgili olduğu varlığın ID'si (rapordan).
        entity_name: Varlığın adı (okunabilirlik için).
        action: Önerilen aksiyon: pause, activate, scale_up, reduce_budget,
            reallocate_budget, clone_winner, test_lookalike, refresh_creative,
            new_audience veya other.
        reason: Kısa gerekçe (ör. 'CPA hedefin 2 katı, frekans yüksek').
        metric_name: İzlenecek metrik: roas, cpa, ctr, cpm, cpc, frequency, spend
            veya purchases (opsiyonel ama önerilir).
        metric_value: O anki metrik değeri (sonradan karşılaştırma için).
    """
    return _log_recommendation(
        level, entity_id, entity_name, action, reason, metric_name, metric_value
    )


@function_tool
def review_recommendations(date_preset: str = "last_7d") -> str:
    """Geçmişte kaydedilen açık önerileri güncel metriklerle karşılaştırıp sonuçlarını gösterir.

    'Geçen sefer ne önermiştin / önerilerin işe yaradı mı / takip et' türü
    sorularda kullan. Her açık öneri için varlığın güncel durumunu ve (metrik
    kaydedildiyse) metriğin nasıl değiştiğini özetler.

    Args:
        date_preset: Güncel metrikler hangi dönemden alınsın (varsayılan last_7d).
    """
    return _review_recommendations(date_preset)


@function_tool
def show_metric_history(
    level: str,
    entity: str,
    metric: str = "roas",
    days: int = 30,
) -> str:
    """Bir varlığın bir metriğinin kayıtlı geçmişini (uzun dönem trend) gösterir.

    Meta'nın hazır dönemlerinden bağımsız, biriken snapshot geçmişine dayanır.
    'Bu kampanyanın ROAS'ı zaman içinde nasıl gitti' gibi sorularda kullan.

    Args:
        level: account, campaign, adset veya ad.
        entity: Varlık adı veya ID'si (account seviyesinde 'account').
        metric: roas, cpa, ctr, cpm, cpc, frequency, spend veya purchases.
        days: En fazla kaç günlük geçmiş gösterilsin (varsayılan 30).
    """
    return _show_metric_history(level, entity, metric, days)


@function_tool
def mark_recommendation(rec_id: int, status: str, note: str = "") -> str:
    """Kaydedilen bir öneriyi 'followed' (uygulandı) veya 'dismissed' (geçersiz) işaretler.

    review_recommendations çıktısındaki öneri numarasını (#id) kullan.

    Args:
        rec_id: Önerinin numarası.
        status: 'followed', 'dismissed' veya 'open'.
        note: İsteğe bağlı sonuç notu.
    """
    return _mark_recommendation(rec_id, status, note)
