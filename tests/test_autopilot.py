from app.meta import autopilot, history


def test_review_pause_applied_marks_followed() -> None:
    open_recs = [
        {"id": 1, "entity_id": "a1", "entity_name": "X", "action": "pause",
         "created_on": "2026-06-10", "metric_name": "roas", "metric_value": 0.0},
    ]
    current = {"a1": {"id": "a1", "status": "PAUSED", "spend": 0, "roas": 0}}
    out = autopilot.review_open_recommendations(open_recs, current)
    assert out[0]["mark_followed"] is True
    assert "uygulanmış" in out[0]["line"]


def test_review_pause_still_active_flags_bleeding() -> None:
    open_recs = [
        {"id": 1, "entity_id": "a1", "entity_name": "X", "action": "pause",
         "created_on": "2026-06-10", "metric_name": "roas", "metric_value": 0.0},
    ]
    current = {"a1": {"id": "a1", "status": "ACTIVE", "spend": 1500, "roas": 0.4}}
    out = autopilot.review_open_recommendations(open_recs, current)
    assert out[0]["mark_followed"] is False
    assert "hâlâ açık" in out[0]["line"] and "1,500" in out[0]["line"]


def test_review_missing_entity() -> None:
    open_recs = [
        {"id": 1, "entity_id": "gone", "entity_name": "X", "action": "pause",
         "created_on": "2026-06-10"},
    ]
    out = autopilot.review_open_recommendations(open_recs, {})
    assert out[0]["mark_followed"] is False
    assert "raporda yok" in out[0]["line"]


def test_review_non_pause_uses_metric_outcome() -> None:
    open_recs = [
        {"id": 2, "entity_id": "c1", "entity_name": "Kampanya", "action": "scale_up",
         "created_on": "2026-06-10", "metric_name": "roas", "metric_value": 2.0},
    ]
    current = {"c1": {"id": "c1", "status": "ACTIVE", "roas": 3.0}}
    out = autopilot.review_open_recommendations(open_recs, current)
    assert "ROAS" in out[0]["line"] and "iyileşti" in out[0]["line"]


def test_review_pause_recovered_marks_followed() -> None:
    # Bleeder durdurulmadı ama ROAS toparlandı -> takip kapanır.
    open_recs = [
        {"id": 1, "entity_id": "a1", "entity_name": "X", "action": "pause",
         "created_on": "2026-06-10", "metric_name": "roas", "metric_value": 0.7},
    ]
    current = {"a1": {"id": "a1", "status": "ACTIVE", "spend": 800, "roas": 2.4}}
    out = autopilot.review_open_recommendations(open_recs, current)
    assert out[0]["mark_followed"] is True
    assert "toparlandı" in out[0]["line"]


def test_format_review_section_empty() -> None:
    assert autopilot.format_review_section([]) == ""


def test_select_pause_candidates_filters() -> None:
    recs = [
        {"id": "a1", "name": "X", "recommendation": "Kapatılmaya aday", "reason": "...", "roas": 0},
        {"id": "a2", "name": "Y", "recommendation": "İyi performans", "roas": 5},
        {"id": "a3", "name": "W", "recommendation": "Bütçeyi azalt veya reklamı kapat", "roas": 0.4},
        {"id": "-", "name": "Z", "recommendation": "Kapatılmaya aday", "roas": 0},  # id yok
    ]
    out = autopilot.select_pause_candidates(recs)
    assert [c["id"] for c in out] == ["a1", "a3"]  # iki bleeder türü de


def test_log_new_pause_candidates_dedups() -> None:
    conn = history.connect(":memory:")
    candidates = [
        {"id": "a1", "name": "X", "reason": "satışsız", "roas": 0},
        {"id": "a2", "name": "Y", "reason": "düşük roas", "roas": 0.5},
    ]
    open_recs = [{"entity_id": "a1", "action": "pause"}]  # a1 zaten açık
    logged = autopilot.log_new_pause_candidates(conn, candidates, open_recs, account_id="act_1")
    assert logged == 1  # sadece a2 yeni
    rows = history.list_recommendations(conn, status="open", account_id="act_1")
    assert {r["entity_id"] for r in rows} == {"a2"}
