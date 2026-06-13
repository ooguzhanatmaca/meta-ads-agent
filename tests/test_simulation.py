from app.meta.simulation import account_totals, format_simulation, simulate


ROWS = [
    {"name": "Kampanya A", "spend": 1000, "purchases": 10, "purchase_value": 5000, "clicks": 200, "impressions": 10000},
    {"name": "Kampanya B", "spend": 500, "purchases": 2, "purchase_value": 600, "clicks": 100, "impressions": 8000},
]


def test_account_totals() -> None:
    totals = account_totals(ROWS)
    assert totals["spend"] == 1500
    assert totals["purchases"] == 12
    assert totals["purchase_value"] == 5600
    assert round(totals["roas"], 2) == round(5600 / 1500, 2)


def test_simulate_budget_increase_scales_target() -> None:
    result = simulate(ROWS, "Kampanya A", change_pct=50)
    # A %50 artınca harcama 1000->1500, toplam 1500->2000.
    assert result["after"]["spend"] == 2000
    assert result["after"]["purchase_value"] == 5000 * 1.5 + 600
    assert "Bütçe" in result["action"]


def test_simulate_pause_removes_target() -> None:
    result = simulate(ROWS, "Kampanya B", pause=True)
    # B kapanınca sadece A kalır.
    assert result["after"]["spend"] == 1000
    assert result["after"]["purchases"] == 10
    # B verimsizdi; kapatınca hesap ROAS yükselmeli.
    assert result["after"]["roas"] > result["before"]["roas"]
    assert result["action"] == "Kapatma"


def test_simulate_unknown_target_returns_none() -> None:
    assert simulate(ROWS, "Olmayan Kampanya", change_pct=10) is None


def test_partial_name_match() -> None:
    result = simulate(ROWS, "kampanya a", change_pct=10)
    assert result["target"] == "Kampanya A"


def test_format_simulation_contains_before_after() -> None:
    text = format_simulation(simulate(ROWS, "Kampanya A", change_pct=20))
    assert "ROAS" in text and "→" in text
    assert "Tahmindir" in text
