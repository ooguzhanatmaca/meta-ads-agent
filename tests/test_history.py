from app.meta import history


def _conn():
    return history.connect(":memory:")


def test_save_snapshot_is_idempotent_per_day() -> None:
    conn = _conn()
    rows = [{"id": "c1", "name": "Kampanya A", "status": "ACTIVE", "roas": 3.0, "cpa": 100.0}]
    history.save_snapshot(conn, "campaign", rows, taken_on="2026-06-10")
    # Same day, new values -> overwrite, not duplicate.
    rows[0]["roas"] = 4.0
    history.save_snapshot(conn, "campaign", rows, taken_on="2026-06-10")

    series = history.metric_history(conn, "campaign", "c1", "roas")
    assert len(series) == 1
    assert series[0]["value"] == 4.0


def test_metric_history_returns_oldest_first() -> None:
    conn = _conn()
    for day, roas in (("2026-06-10", 2.0), ("2026-06-12", 3.0), ("2026-06-11", 2.5)):
        history.save_snapshot(
            conn, "account", [{"id": "account", "name": "Hesap", "roas": roas}], taken_on=day
        )
    series = history.metric_history(conn, "account", "account", "roas")
    assert [p["taken_on"] for p in series] == ["2026-06-10", "2026-06-11", "2026-06-12"]
    assert [p["value"] for p in series] == [2.0, 2.5, 3.0]


def test_metric_history_rejects_unknown_metric() -> None:
    conn = _conn()
    try:
        history.metric_history(conn, "account", "account", "made_up")
    except ValueError as error:
        assert "made_up" in str(error)
    else:  # pragma: no cover
        raise AssertionError("ValueError bekleniyordu")


def test_find_entity_id_resolves_partial_name() -> None:
    conn = _conn()
    history.save_snapshot(
        conn, "ad", [{"id": "a99", "name": "Yaz Kampanyası - Video", "roas": 1.0}],
        taken_on="2026-06-10",
    )
    found = history.find_entity_id(conn, "ad", "Yaz")
    assert found == {"entity_id": "a99", "entity_name": "Yaz Kampanyası - Video"}
    assert history.find_entity_id(conn, "ad", "yok") is None


def test_record_and_list_recommendations() -> None:
    conn = _conn()
    rec_id = history.record_recommendation(
        conn,
        level="ad",
        entity_id="a1",
        entity_name="Reklam X",
        action="pause",
        reason="CPA çok yüksek",
        metric_name="cpa",
        metric_value=250.0,
        created_on="2026-06-10",
    )
    assert rec_id == 1
    open_recs = history.list_recommendations(conn, status="open")
    assert len(open_recs) == 1
    assert open_recs[0]["action"] == "pause"
    assert open_recs[0]["metric_value"] == 250.0


def test_update_recommendation_status() -> None:
    conn = _conn()
    rec_id = history.record_recommendation(
        conn, level="ad", entity_id="a1", entity_name="X", action="pause"
    )
    assert history.update_recommendation(conn, rec_id, status="followed", outcome_note="ok")
    assert history.list_recommendations(conn, status="open") == []
    followed = history.list_recommendations(conn, status="followed")
    assert followed[0]["outcome_note"] == "ok"


def test_update_recommendation_rejects_bad_status() -> None:
    conn = _conn()
    rec_id = history.record_recommendation(
        conn, level="ad", entity_id="a1", entity_name="X", action="pause"
    )
    try:
        history.update_recommendation(conn, rec_id, status="garbage")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("ValueError bekleniyordu")


def test_update_recommendation_missing_id_returns_false() -> None:
    conn = _conn()
    assert history.update_recommendation(conn, 999, status="followed") is False


def test_evaluate_outcome_cost_metric_lower_is_better() -> None:
    # CPA dropped 250 -> 180: improvement for a cost metric.
    result = history.evaluate_outcome("cpa", 250.0, 180.0)
    assert result["verdict"] == "iyileşti"
    assert result["delta_pct"] < 0


def test_evaluate_outcome_value_metric_higher_is_better() -> None:
    # ROAS rose 2.0 -> 3.0: improvement for a value metric.
    result = history.evaluate_outcome("roas", 2.0, 3.0)
    assert result["verdict"] == "iyileşti"
    assert result["delta_pct"] > 0


def test_evaluate_outcome_small_change_is_neutral() -> None:
    result = history.evaluate_outcome("roas", 2.0, 2.05)
    assert result["verdict"] == "nötr"


def test_evaluate_outcome_handles_missing_data() -> None:
    assert history.evaluate_outcome("", None, None)["verdict"] == "bilinmiyor"
    assert history.evaluate_outcome("cpa", 0.0, 5.0)["verdict"] == "bilinmiyor"
