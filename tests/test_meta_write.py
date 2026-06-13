from unittest.mock import patch

import pytest

from app.tools import meta_write as mw


def test_writes_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENABLE_WRITE_ACTIONS", raising=False)
    assert mw._writes_enabled() is False


def test_writes_enabled_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("true", "1", "yes", "evet", "TRUE"):
        monkeypatch.setenv("ENABLE_WRITE_ACTIONS", value)
        assert mw._writes_enabled() is True
    for value in ("false", "0", "no", ""):
        monkeypatch.setenv("ENABLE_WRITE_ACTIONS", value)
        assert mw._writes_enabled() is False


def test_create_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "false")
    with patch.object(mw, "create_campaign") as create:
        out = mw._create_paused_campaign("Test", "OUTCOME_SALES")
    assert create.called is False  # API'ye hiç gidilmemeli
    assert "KAPALI" in out


def test_create_paused_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    calls = {}

    def fake_create(name, objective, status):
        calls.update(name=name, objective=objective, status=status)
        return {"id": "120000123"}

    with patch.object(mw, "create_campaign", side_effect=fake_create):
        out = mw._create_paused_campaign("Test", "OUTCOME_SALES")

    assert calls["status"] == "PAUSED"  # daima duraklatılmış
    assert calls["objective"] == "OUTCOME_SALES"
    assert "DURAKLATILMIŞ" in out and "120000123" in out


def test_invalid_objective_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    with patch.object(mw, "create_campaign") as create:
        out = mw._create_paused_campaign("Test", "GECERSIZ")
    assert create.called is False
    assert "Geçersiz hedef" in out


def test_pause_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "false")
    with patch.object(mw, "set_entity_status") as status:
        out = mw._pause_entity("123")
    assert status.called is False
    assert "KAPALI" in out


def test_pause_sets_paused_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    with patch.object(mw, "set_entity_status") as status:
        out = mw._pause_entity("123")
    status.assert_called_once_with("123", "PAUSED")
    assert "duraklat" in out.lower()


def test_activate_sets_active_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    with patch.object(mw, "set_entity_status") as status:
        out = mw._activate_entity("123")
    status.assert_called_once_with("123", "ACTIVE")


def test_budget_converts_tl_to_minor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    with patch.object(mw, "set_daily_budget") as budget:
        out = mw._update_daily_budget("123", 500)
    budget.assert_called_once_with("123", 50000)  # 500 TL -> 50000 kuruş
    assert "500" in out


def test_budget_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "false")
    with patch.object(mw, "set_daily_budget") as budget:
        out = mw._update_daily_budget("123", 500)
    assert budget.called is False
    assert "KAPALI" in out
