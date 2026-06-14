"""Autopilot v1 — closes the loop in the daily e-mail (recommendations only).

The daily report already e-mails a prioritized action list. Autopilot adds two
things on top, using the persistent recommendation journal (``app.meta.history``):

1. **Review** — for every still-open recommendation, compare against current data
   and report the outcome ("you paused it, spend stopped" / "still active and
   still bleeding").
2. **Log** — record today's clear pause candidates so tomorrow's e-mail can track
   whether they were acted on.

No account changes are ever made here — this only reads, reports, and journals.
The functions that do the judging are pure (they take rows + a DB connection), so
they are easy to test; the thin orchestrator does the Meta fetching.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from app.meta import history


# "Durdur/azalt" türü bleeder önerileri — Autopilot bunları izler.
PAUSE_LABELS = {"Kapatılmaya aday", "Bütçeyi azalt veya reklamı kapat"}

# Bir bleeder'ın "toparlandı" sayılması için gereken sağlıklı ROAS eşiği.
HEALTHY_ROAS = 1.5


def review_open_recommendations(
    open_recs: list[dict[str, Any]],
    current_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Judge each open recommendation against current data. Pure.

    Returns a list of {rec_id, line, mark_followed} dicts. ``mark_followed`` is
    True when the advice was clearly applied (e.g. a pause recommendation whose
    entity is now PAUSED), so the caller can close it in the journal.
    """
    results: list[dict[str, Any]] = []
    for rec in open_recs:
        entity_id = str(rec.get("entity_id"))
        name = rec.get("entity_name") or entity_id
        action = rec.get("action") or "-"
        created = rec.get("created_on") or "-"
        row = current_by_id.get(entity_id)
        head = f"'{name}' ({created} önerisi: {action})"

        if row is None:
            line = f"   {head} → varlık güncel raporda yok (durdurulmuş/silinmiş olabilir)."
            results.append({"rec_id": rec.get("id"), "line": line, "mark_followed": False})
            continue

        status = str(row.get("status") or "-").upper()
        if action == "pause":
            roas_now = float(row.get("roas") or 0)
            roas_then = float(rec.get("metric_value") or 0)
            if status == "PAUSED":
                line = f"   ✅ {head} → uygulanmış (durduruldu); harcama durdu."
                results.append({"rec_id": rec.get("id"), "line": line, "mark_followed": True})
            elif roas_now >= HEALTHY_ROAS and roas_now > roas_then:
                line = (
                    f"   ✅ {head} → toparlandı; ROAS {roas_then:.2f} → {roas_now:.2f}. "
                    "Müdahale gerekmiyor."
                )
                results.append({"rec_id": rec.get("id"), "line": line, "mark_followed": True})
            else:
                spend = float(row.get("spend") or 0)
                line = (
                    f"   ⚠️ {head} → hâlâ açık ve verimsiz; son 7 günde {spend:,.0f} TL "
                    f"harcadı, ROAS {roas_now:.2f}. Durdurulması/azaltılması önerilir."
                )
                results.append({"rec_id": rec.get("id"), "line": line, "mark_followed": False})
            continue

        # Diğer öneri türleri: kayıtlı metriği güncelle karşılaştır.
        metric = rec.get("metric_name") or ""
        if metric and metric in history.TRACKED_METRICS:
            outcome = history.evaluate_outcome(
                metric, rec.get("metric_value"), float(row.get(metric) or 0)
            )
            line = f"   {head} → {outcome['note']}"
        else:
            line = f"   {head} → güncel durum: {status}."
        results.append({"rec_id": rec.get("id"), "line": line, "mark_followed": False})
    return results


def format_review_section(lines: list[str]) -> str:
    """Render the review lines as an e-mail section (empty string if none)."""
    if not lines:
        return ""
    return "\n".join(["GEÇMİŞ ÖNERİLERİN SONUCU:", "", *lines])


def select_pause_candidates(recommendations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """From evaluate_ads output, the clear 'should pause' items (with an id)."""
    return [
        r
        for r in recommendations
        if r.get("recommendation") in PAUSE_LABELS and r.get("id") and r.get("id") != "-"
    ]


def log_new_pause_candidates(
    conn: sqlite3.Connection,
    candidates: list[dict[str, Any]],
    open_recs: list[dict[str, Any]],
    *,
    account_id: str = "-",
    created_on: str | None = None,
) -> int:
    """Journal pause candidates that aren't already open (dedup by entity+action).

    Returns the number newly logged.
    """
    already_open = {
        (str(r.get("entity_id")), r.get("action")) for r in open_recs
    }
    logged = 0
    for cand in candidates:
        key = (str(cand.get("id")), "pause")
        if key in already_open:
            continue
        history.record_recommendation(
            conn,
            level="ad",
            entity_id=str(cand.get("id")),
            entity_name=str(cand.get("name") or "-"),
            action="pause",
            reason=str(cand.get("reason") or ""),
            metric_name="roas",
            metric_value=float(cand.get("roas") or 0),
            account_id=account_id,
            created_on=created_on,
        )
        already_open.add(key)
        logged += 1
    return logged


def build_autopilot_section() -> str:
    """Orchestrate review + logging and return the e-mail section text.

    Best-effort: any failure returns an empty string so the report still sends.
    """
    from app.meta.client import MetaClient, get_performance_report
    from app.meta.performance_report import calculate_report_rows
    from app.rules.performance_rules import evaluate_ads

    try:
        account_id = MetaClient.from_env().ad_account_id
    except Exception:  # noqa: BLE001
        account_id = "-"

    try:
        ad_rows = calculate_report_rows(get_performance_report("ad", "last_7d"))
    except Exception as error:  # noqa: BLE001
        return f"AUTOPILOT: güncel veri alınamadı ({error})."

    current_by_id = {str(row["id"]): row for row in ad_rows}
    recommendations = evaluate_ads(ad_rows)

    conn = history.connect()
    try:
        open_recs = history.list_recommendations(conn, status="open", account_id=account_id)
        verdicts = review_open_recommendations(open_recs, current_by_id)
        for verdict in verdicts:
            if verdict["mark_followed"] and verdict["rec_id"] is not None:
                history.update_recommendation(
                    conn, int(verdict["rec_id"]), status="followed",
                    outcome_note="Autopilot: uygulanmış (durduruldu).",
                )
        logged = log_new_pause_candidates(
            conn, select_pause_candidates(recommendations), open_recs,
            account_id=account_id,
        )
    finally:
        conn.close()

    parts = [format_review_section([v["line"] for v in verdicts])]
    if logged:
        parts.append(
            f"AUTOPILOT: bugün {logged} yeni 'kapatılmaya aday' reklam izlemeye "
            "alındı; yarınki raporda sonuçları takip edilecek."
        )
    return "\n\n".join(part for part in parts if part)
