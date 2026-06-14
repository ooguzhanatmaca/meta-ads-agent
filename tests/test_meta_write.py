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


def test_budget_dry_run_previews_without_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    fake = {"name": "Kampanya A", "status": "ACTIVE", "daily_budget": "120000"}  # 1200 TL
    with patch.object(mw, "get_entity", return_value=fake) as read, \
            patch.object(mw, "set_daily_budget") as budget:
        out = mw._update_daily_budget("123", 3000, dry_run=True)
    assert budget.called is False           # hiçbir yazma yapılmadı
    assert read.called is True
    assert "ÖNİZLEME" in out
    assert "1200" in out and "3000" in out   # mevcut -> yeni
    assert "+150" in out                     # %150 artış


def test_budget_dry_run_works_without_current_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    with patch.object(mw, "get_entity", side_effect=mw.MetaAPIError("yok")), \
            patch.object(mw, "set_daily_budget") as budget:
        out = mw._update_daily_budget("123", 3000, dry_run=True)
    assert budget.called is False
    assert "ÖNİZLEME" in out and "3000" in out


def test_activate_dry_run_shows_spend_exposure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    fake = {"name": "Set B", "status": "PAUSED", "daily_budget": "50000"}  # 500 TL
    with patch.object(mw, "get_entity", return_value=fake), \
            patch.object(mw, "set_entity_status") as status:
        out = mw._activate_entity("123", dry_run=True)
    assert status.called is False
    assert "ÖNİZLEME" in out and "YAYINA" in out and "500" in out


def test_pause_dry_run_does_not_write(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    with patch.object(mw, "get_entity", return_value={"name": "X"}), \
            patch.object(mw, "set_entity_status") as status:
        out = mw._pause_entity("123", dry_run=True)
    assert status.called is False
    assert "ÖNİZLEME" in out and "DURAKLATILACAK" in out


def test_ad_set_creates_paused_with_budget_conversion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    calls = {}

    def fake_create_ad_set(campaign_id, name, minor, **kwargs):
        calls.update(campaign_id=campaign_id, name=name, minor=minor, kwargs=kwargs)
        return {"id": "23800"}

    with patch.object(mw, "create_ad_set", side_effect=fake_create_ad_set):
        out = mw._create_ad_set("12090", "Set A", 300, country="TR", age_min=25, age_max=45)

    assert calls["campaign_id"] == "12090"
    assert calls["minor"] == 30000  # 300 TL -> 30000 kuruş
    assert calls["kwargs"]["age_min"] == 25
    assert calls["kwargs"]["genders"] is None  # cinsiyet verilmezse tümü
    assert "DURAKLATILMIŞ" in out and "23800" in out


def test_ad_set_maps_gender_to_meta_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    calls = {}

    def fake_create_ad_set(campaign_id, name, minor, **kwargs):
        calls.update(kwargs=kwargs)
        return {"id": "1"}

    with patch.object(mw, "create_ad_set", side_effect=fake_create_ad_set):
        out_m = mw._create_ad_set("c", "Erkek Set", 300, gender="erkek")
    assert calls["kwargs"]["genders"] == (1,)  # erkek -> 1
    assert "cinsiyet erkek" in out_m

    with patch.object(mw, "create_ad_set", side_effect=fake_create_ad_set):
        mw._create_ad_set("c", "Kadın Set", 300, gender="female")
    assert calls["kwargs"]["genders"] == (2,)  # female -> 2


def test_genders_from_mapping() -> None:
    assert mw._genders_from("erkek") == ((1,), "erkek")
    assert mw._genders_from("KADIN") == ((2,), "kadın")
    assert mw._genders_from("all") == (None, "tümü")
    assert mw._genders_from("") == (None, "tümü")


def test_parse_interest_ids() -> None:
    assert mw._parse_interest_ids("6003, 6004 ,, 6005") == (
        {"id": "6003"}, {"id": "6004"}, {"id": "6005"},
    )
    assert mw._parse_interest_ids("") == ()


def test_ad_set_passes_interests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    calls = {}

    def fake_create_ad_set(campaign_id, name, minor, **kwargs):
        calls.update(kwargs=kwargs)
        return {"id": "1"}

    with patch.object(mw, "create_ad_set", side_effect=fake_create_ad_set):
        out = mw._create_ad_set("c", "Set", 300, interest_ids="6003150119230,6003299417538")
    assert calls["kwargs"]["interests"] == ({"id": "6003150119230"}, {"id": "6003299417538"})
    assert "2 ilgi alanı" in out


def test_ad_set_no_interests_passes_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    calls = {}

    def fake_create_ad_set(campaign_id, name, minor, **kwargs):
        calls.update(kwargs=kwargs)
        return {"id": "1"}

    with patch.object(mw, "create_ad_set", side_effect=fake_create_ad_set):
        mw._create_ad_set("c", "Set", 300)
    assert calls["kwargs"]["interests"] is None


def test_budget_ceiling_blocks_typo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    monkeypatch.setenv("MAX_DAILY_BUDGET_TRY", "50000")
    # 300.000 TL (3.000 yerine yazım hatası) -> tavanı aşar, yazma yapılmaz.
    with patch.object(mw, "set_daily_budget") as budget:
        out = mw._update_daily_budget("123", 300000)
    assert budget.called is False
    assert "Güvenlik tavanı" in out
    with patch.object(mw, "create_ad_set") as create:
        out2 = mw._create_ad_set("c", "Set", 300000)
    assert create.called is False
    assert "Güvenlik tavanı" in out2


def test_budget_ceiling_allows_normal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    monkeypatch.setenv("MAX_DAILY_BUDGET_TRY", "50000")
    with patch.object(mw, "set_daily_budget") as budget:
        out = mw._update_daily_budget("123", 3000)
    budget.assert_called_once()
    assert "Güvenlik tavanı" not in out


def test_budget_ceiling_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    monkeypatch.setenv("MAX_DAILY_BUDGET_TRY", "1000")
    with patch.object(mw, "set_daily_budget") as budget:
        out = mw._update_daily_budget("123", 3000)  # 1000 tavanını aşar
    assert budget.called is False
    assert "Güvenlik tavanı" in out


def test_ad_set_invalid_goal_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    with patch.object(mw, "create_ad_set") as create:
        out = mw._create_ad_set("1", "Set", 100, optimization_goal="GECERSIZ")
    assert create.called is False
    assert "Geçersiz" in out


def test_ad_set_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "false")
    with patch.object(mw, "create_ad_set") as create:
        out = mw._create_ad_set("1", "Set", 100)
    assert create.called is False
    assert "KAPALI" in out


def test_ad_creates_paused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    with patch.object(mw, "create_ad", return_value={"id": "67800"}) as create:
        out = mw._create_ad("23800", "Reklam A", "creative_999")
    create.assert_called_once_with("23800", "Reklam A", "creative_999")
    assert "DURAKLATILMIŞ" in out and "67800" in out


def test_ad_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "false")
    with patch.object(mw, "create_ad") as create:
        out = mw._create_ad("1", "Reklam", "c1")
    assert create.called is False
    assert "KAPALI" in out


def test_clone_ad_set_passes_params_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    calls = {}

    def fake_clone(source_id, new_name, multiplier, campaign_id):
        calls.update(source_id=source_id, new_name=new_name, multiplier=multiplier,
                     campaign_id=campaign_id)
        return {"id": "99001"}

    with patch.object(mw, "clone_ad_set", side_effect=fake_clone):
        out = mw._clone_ad_set("23800", "Kazanan Kopya", 1.5)

    assert calls["source_id"] == "23800"
    assert calls["multiplier"] == 1.5
    assert calls["campaign_id"] is None  # boş string -> None
    assert "kopyalanarak" in out and "99001" in out


def test_clone_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "false")
    with patch.object(mw, "clone_ad_set") as clone:
        out = mw._clone_ad_set("1", "Kopya")
    assert clone.called is False
    assert "KAPALI" in out


def test_lookalike_creates_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    with patch.object(mw, "create_lookalike_audience", return_value={"id": "aud_1"}) as create:
        out = mw._create_lookalike_audience("src_1", "Benzer Kitle", "TR", 0.02)
    create.assert_called_once_with("src_1", "Benzer Kitle", "TR", 0.02)
    assert "aud_1" in out


def test_lookalike_rejects_bad_ratio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "true")
    with patch.object(mw, "create_lookalike_audience") as create:
        out = mw._create_lookalike_audience("src_1", "X", "TR", 0.5)
    assert create.called is False
    assert "ratio" in out.lower() or "oran" in out.lower()


def test_lookalike_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_WRITE_ACTIONS", "false")
    with patch.object(mw, "create_lookalike_audience") as create:
        out = mw._create_lookalike_audience("src_1", "X")
    assert create.called is False
    assert "KAPALI" in out
