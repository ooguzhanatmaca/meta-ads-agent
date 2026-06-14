"""Deterministic rules that judge conversion-tracking (pixel) health.

Pure functions: they take already-parsed pixel data (event totals + how long
since the pixel last fired) and return a prioritized list of issues. Fetching and
time math live in :mod:`app.meta.tracking_health`, so these stay easy to test.

Each pixel dict is expected to look like::

    {
        "name": str,
        "is_unavailable": bool,
        "hours_since_fired": float | None,   # None = never fired / unknown
        "events": {"PageView": 799, "Purchase": 6, ...},
    }
"""

from typing import Any


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "info": 3}

# How many hours without data before we flag a pixel as stale.
STALE_HOURS = 24.0


def _issue(severity: str, title: str, detail: str) -> dict[str, str]:
    return {"severity": severity, "title": title, "detail": detail}


def evaluate_pixel(pixel: dict[str, Any]) -> list[dict[str, str]]:
    """Return all issues matched by a single parsed pixel."""
    name = str(pixel.get("name") or "Piksel")
    issues: list[dict[str, str]] = []

    if pixel.get("is_unavailable"):
        issues.append(
            _issue("critical", f"'{name}' pikseli kullanılamıyor",
                   "Piksel devre dışı veya erişilemez durumda; hiçbir dönüşüm ölçülemez.")
        )
        return issues

    hours = pixel.get("hours_since_fired")
    if hours is None:
        issues.append(
            _issue("critical", f"'{name}' hiç veri göndermemiş",
                   "Piksel kurulu ama hiç olay almamış; izleme tamamen kör.")
        )
    elif hours > STALE_HOURS:
        days = hours / 24
        ago = f"{days:.1f} gün" if days >= 1 else f"{hours:.0f} saat"
        issues.append(
            _issue("high", f"'{name}' {ago}dır veri göndermiyor",
                   "Piksel beklenenden uzun süredir sessiz; site kodu bozulmuş olabilir.")
        )

    events = pixel.get("events") or {}
    total = sum(int(v or 0) for v in events.values())
    pageview = int(events.get("PageView") or 0)
    add_to_cart = int(events.get("AddToCart") or 0)
    checkout = int(events.get("InitiateCheckout") or 0)
    purchase = int(events.get("Purchase") or 0)

    if total == 0:
        if hours is not None:  # not already covered by the "never fired" case
            issues.append(
                _issue("critical", f"'{name}' seçilen dönemde hiç olay almadı",
                       "Ölçüm penceresinde tek bir olay bile yok.")
            )
        return _sorted(issues)

    if purchase == 0:
        if add_to_cart > 0 or checkout > 0:
            # Sepete ekleme/ödeme var ama satın alma kaydı yok: huni büyük olasılıkla kopuk.
            issues.append(
                _issue("critical", f"'{name}': sepete ekleme/ödeme var, satın alma yok",
                       f"Sepete ekleme {add_to_cart}, ödeme başlatma {checkout} olmasına "
                       "rağmen Purchase olayı yok. Satın alma izlemesi büyük olasılıkla "
                       "bozuk; ROAS ve satın alma optimizasyonu güvenilmez.")
            )
        elif pageview > 0 or total > 0:
            # Yalnızca üst-huni olayları: ya gerçekten satış yok ya izleme eksik.
            issues.append(
                _issue("high", f"'{name}': satın alma olayı gelmiyor",
                       "Trafik ölçülüyor ama Purchase olayı yok. Ya bu dönemde satış "
                       "olmadı ya da satın alma olayı kurulumu eksik; kontrol edin.")
            )

    # Huni kaybı çok dik (ödeme başlatanların çok azı satın alıyor).
    if checkout >= 10 and purchase > 0 and purchase / checkout < 0.10:
        issues.append(
            _issue("medium", f"'{name}': ödeme-satın alma kaybı yüksek",
                   f"Ödeme başlatan {checkout} kişiye karşı {purchase} satın alma "
                   "(%10'un altı); ödeme akışında kayıp veya ölçüm sorunu olabilir.")
        )

    if not issues:
        issues.append(
            _issue("info", f"'{name}': izleme sağlıklı görünüyor",
                   f"Son veri taze, dönemde {purchase} satın alma olayı kaydedildi.")
        )
    return _sorted(issues)


def evaluate_tracking(pixels: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Evaluate every pixel; return issues ordered by severity."""
    if not pixels:
        return [
            _issue("critical", "Hesapta izleme pikseli bulunamadı",
                   "Dönüşüm ölçümü için en az bir piksel/dataset gerekir; aksi halde "
                   "satın alma optimizasyonu ve ROAS verisi güvenilmez olur.")
        ]
    all_issues = [issue for pixel in pixels for issue in evaluate_pixel(pixel)]
    return _sorted(all_issues)


def _sorted(issues: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(issues, key=lambda item: PRIORITY_ORDER.get(item["severity"], 9))
