from app.rules.tracking_rules import evaluate_pixel, evaluate_tracking


def _severities(issues):
    return [issue["severity"] for issue in issues]


def test_no_pixels_is_critical() -> None:
    issues = evaluate_tracking([])
    assert len(issues) == 1
    assert issues[0]["severity"] == "critical"
    assert "bulunamadı" in issues[0]["title"]


def test_unavailable_pixel_is_critical_and_short_circuits() -> None:
    issues = evaluate_pixel({"name": "P", "is_unavailable": True, "events": {}})
    assert _severities(issues) == ["critical"]
    assert "kullanılamıyor" in issues[0]["title"]


def test_never_fired_is_critical() -> None:
    issues = evaluate_pixel(
        {"name": "P", "hours_since_fired": None, "events": {}}
    )
    assert any(i["severity"] == "critical" and "hiç veri" in i["title"] for i in issues)


def test_stale_pixel_flagged_high() -> None:
    issues = evaluate_pixel(
        {"name": "P", "hours_since_fired": 50, "events": {"PageView": 10, "Purchase": 1}}
    )
    assert any(i["severity"] == "high" and "veri göndermiyor" in i["title"] for i in issues)


def test_cart_without_purchase_is_critical() -> None:
    # Sepete ekleme var ama satın alma yok -> izleme bozuk (kritik).
    issues = evaluate_pixel(
        {
            "name": "P",
            "hours_since_fired": 2,
            "events": {"PageView": 500, "AddToCart": 20, "Purchase": 0},
        }
    )
    assert any(
        i["severity"] == "critical" and "satın alma yok" in i["title"] for i in issues
    )


def test_only_pageviews_no_purchase_is_high_not_critical() -> None:
    # Yalnızca üst-huni: satış olmamış olabilir -> kurt masalı anlatma (yüksek).
    issues = evaluate_pixel(
        {
            "name": "P",
            "hours_since_fired": 2,
            "events": {"PageView": 300, "ViewContent": 50, "Purchase": 0},
        }
    )
    assert any(
        i["severity"] == "high" and "satın alma olayı gelmiyor" in i["title"]
        for i in issues
    )
    assert not any(i["severity"] == "critical" for i in issues)


def test_steep_checkout_loss_is_medium() -> None:
    issues = evaluate_pixel(
        {
            "name": "P",
            "hours_since_fired": 1,
            "events": {"PageView": 1000, "InitiateCheckout": 100, "Purchase": 3},
        }
    )
    assert any(i["severity"] == "medium" and "kaybı" in i["title"] for i in issues)


def test_healthy_pixel_reports_info() -> None:
    issues = evaluate_pixel(
        {
            "name": "P",
            "hours_since_fired": 1,
            "events": {"PageView": 1000, "AddToCart": 50, "InitiateCheckout": 30, "Purchase": 20},
        }
    )
    assert _severities(issues) == ["info"]
    assert "sağlıklı" in issues[0]["title"]


def test_empty_window_is_critical() -> None:
    issues = evaluate_pixel({"name": "P", "hours_since_fired": 5, "events": {}})
    assert any(i["severity"] == "critical" and "hiç olay" in i["title"] for i in issues)


def test_issues_sorted_by_severity() -> None:
    pixels = [
        {"name": "A", "hours_since_fired": 1, "events": {"PageView": 5, "Purchase": 1}},  # info
        {"name": "B", "hours_since_fired": 1, "events": {"AddToCart": 9, "Purchase": 0}},  # critical
    ]
    issues = evaluate_tracking(pixels)
    assert issues[0]["severity"] == "critical"
