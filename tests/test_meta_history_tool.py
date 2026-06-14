from unittest.mock import patch

import pytest

from app.meta import history
from app.tools import meta_history as mh


def test_entity_is_real_skips_account_and_unknown() -> None:
    # Hesap seviyesi / boş id doğrulamadan geçer (engelleme yapma).
    assert mh._entity_is_real("account", "account") is True
    assert mh._entity_is_real("ad", "") is True


def test_entity_is_real_true_when_exists() -> None:
    with patch.object(mh, "get_entity", return_value={"id": "123"}):
        assert mh._entity_is_real("ad", "123") is True


def test_entity_is_real_false_when_missing() -> None:
    with patch.object(mh, "get_entity", side_effect=mh.MetaAPIError("not found")):
        assert mh._entity_is_real("ad", "999") is False


def test_log_recommendation_rejects_fake_entity(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    db = str(tmp_path / "h.db")
    monkeypatch.setenv("HISTORY_DB_PATH", db)
    with patch.object(mh, "get_entity", side_effect=mh.MetaAPIError("not found")):
        out = mh._log_recommendation("ad", "fake999", "Uydurma Reklam", "pause")
    assert "KAYDEDİLMEDİ" in out
    # Hiçbir şey günlüğe yazılmamalı.
    conn = history.connect(db)
    assert history.list_recommendations(conn, status=None) == []


def test_log_recommendation_saves_real_entity(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    db = str(tmp_path / "h.db")
    monkeypatch.setenv("HISTORY_DB_PATH", db)
    with patch.object(mh, "get_entity", return_value={"id": "123"}), \
            patch.object(mh, "_account_id", return_value="act_test"):
        out = mh._log_recommendation(
            "ad", "123", "Gerçek Reklam", "pause", metric_name="roas", metric_value=0.5
        )
    assert "kaydedildi" in out
    conn = history.connect(db)
    rows = history.list_recommendations(conn, status=None, account_id="act_test")
    assert len(rows) == 1 and rows[0]["entity_id"] == "123"
