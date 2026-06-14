"""Audit conversion-tracking (pixel) health: events flowing, freshness, funnel.

Pulls the account's pixels and their recent event breakdown, computes how stale
each pixel is and a simple funnel, then runs deterministic rules
(:mod:`app.rules.tracking_rules`) to surface issues. This is the foundation that
makes every other recommendation trustworthy — bad tracking means bad data.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from app.meta.client import get_pixel_stats, get_pixels
from app.rules.tracking_rules import evaluate_tracking


# Funnel events we care about, in order, for readable output.
FUNNEL_EVENTS = ("PageView", "ViewContent", "AddToCart", "InitiateCheckout", "Purchase")
WINDOW_DAYS = 7


def _parse_time(value: str | None) -> datetime | None:
    """Parse Meta's ISO timestamps (e.g. '2026-06-13T23:59:54+0000')."""
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    # Meta uses '+0000' (no colon); fromisoformat needs '+00:00' on 3.10.
    if len(text) >= 5 and text[-5] in "+-" and text[-3] != ":":
        text = f"{text[:-2]}:{text[-2:]}"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _aggregate_events(stats: list[dict[str, Any]]) -> dict[str, int]:
    """Sum a pixel's per-bucket stats into total counts per event type."""
    totals: dict[str, int] = {}
    for bucket in stats:
        for item in bucket.get("data") or []:
            name = str(item.get("value") or "")
            if not name:
                continue
            totals[name] = totals.get(name, 0) + int(item.get("count") or 0)
    return totals


def collect_tracking_health(now: datetime | None = None) -> dict[str, Any]:
    """Gather parsed pixel data plus rule-based issues for the configured account."""
    reference = now or datetime.now(timezone.utc)
    start_time = (reference - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")

    pixels_raw = get_pixels()
    parsed: list[dict[str, Any]] = []
    for pixel in pixels_raw:
        pixel_id = str(pixel.get("id") or "")
        last_fired = _parse_time(pixel.get("last_fired_time"))
        hours_since = None
        if last_fired is not None:
            hours_since = (reference - last_fired).total_seconds() / 3600

        events: dict[str, int] = {}
        try:
            events = _aggregate_events(get_pixel_stats(pixel_id, start_time))
        except Exception:  # noqa: BLE001 — stats may be unavailable; rules handle empties
            events = {}

        parsed.append(
            {
                "id": pixel_id,
                "name": str(pixel.get("name") or "Piksel"),
                "is_unavailable": bool(pixel.get("is_unavailable")),
                "last_fired_time": pixel.get("last_fired_time"),
                "hours_since_fired": hours_since,
                "events": events,
            }
        )

    return {"pixels": parsed, "issues": evaluate_tracking(parsed)}


def _format_funnel(events: dict[str, int]) -> str:
    parts = []
    for name in FUNNEL_EVENTS:
        if name in events:
            parts.append(f"{name} {events[name]}")
    return " → ".join(parts) if parts else "olay yok"


def format_tracking_health(health: dict[str, Any]) -> str:
    """Render the audit as readable Turkish text."""
    pixels = health.get("pixels") or []
    issues = health.get("issues") or []

    lines = [f"İzleme (piksel) sağlığı — son {WINDOW_DAYS} gün:", ""]

    if not pixels:
        lines.append("Hesapta tanımlı piksel bulunamadı.")
    for pixel in pixels:
        hours = pixel.get("hours_since_fired")
        if hours is None:
            fresh = "hiç tetiklenmemiş"
        elif hours < 1:
            fresh = "son veri <1 saat önce"
        elif hours < 24:
            fresh = f"son veri {hours:.0f} saat önce"
        else:
            fresh = f"son veri {hours / 24:.1f} gün önce"
        lines.append(f"• {pixel['name']} ({fresh})")
        lines.append(f"  Huni: {_format_funnel(pixel.get('events') or {})}")

    severity_label = {"critical": "KRİTİK", "high": "YÜKSEK", "medium": "ORTA", "info": "BİLGİ"}
    lines.append("")
    lines.append("Bulgular:")
    for issue in issues:
        label = severity_label.get(issue["severity"], issue["severity"].upper())
        lines.append(f"  [{label}] {issue['title']} — {issue['detail']}")

    return "\n".join(lines)


def build_tracking_health() -> str:
    return format_tracking_health(collect_tracking_health())
