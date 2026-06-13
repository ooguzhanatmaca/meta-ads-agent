from app.rules.diagnosis_rules import diagnose_account, diagnose_contributors


def test_roas_drop_from_revenue() -> None:
    current = {"roas": 3.0, "purchase_value": 6000, "spend": 2000, "purchases": 10,
               "cpa": 200, "frequency": 2.0, "cpm": 100, "cpc": 5, "ctr": 2.0}
    previous = {"roas": 5.0, "purchase_value": 10000, "spend": 2000, "purchases": 18,
                "cpa": 111, "frequency": 2.0, "cpm": 100, "cpc": 5, "ctr": 2.0}
    causes = diagnose_account(current, previous)
    assert any("Gelir" in c["cause"] for c in causes)


def test_creative_fatigue_detected() -> None:
    current = {"roas": 4.0, "purchase_value": 8000, "spend": 2000, "purchases": 15,
               "cpa": 133, "frequency": 4.0, "cpm": 100, "cpc": 5, "ctr": 1.0}
    previous = {"roas": 4.0, "purchase_value": 8000, "spend": 2000, "purchases": 15,
                "cpa": 133, "frequency": 2.5, "cpm": 100, "cpc": 5, "ctr": 1.0}
    causes = diagnose_account(current, previous)
    assert any("yorgunluğu" in c["cause"] for c in causes)


def test_competition_detected_via_cpm() -> None:
    current = {"roas": 4.0, "purchase_value": 8000, "spend": 2000, "purchases": 15,
               "cpa": 133, "frequency": 2.0, "cpm": 130, "cpc": 5, "ctr": 2.0}
    previous = {"roas": 4.0, "purchase_value": 8000, "spend": 2000, "purchases": 15,
                "cpa": 133, "frequency": 2.0, "cpm": 100, "cpc": 5, "ctr": 2.0}
    causes = diagnose_account(current, previous)
    assert any("rekabet" in c["cause"].lower() for c in causes)


def test_stable_account_no_causes() -> None:
    metrics = {"roas": 5.0, "purchase_value": 10000, "spend": 2000, "purchases": 18,
               "cpa": 111, "frequency": 2.0, "cpm": 100, "cpc": 5, "ctr": 2.0}
    assert diagnose_account(dict(metrics), dict(metrics)) == []


def test_contributors_flag_zero_sale_and_low_roas() -> None:
    rows = [
        {"name": "A", "spend": 800, "roas": 0, "purchases": 0, "frequency": 2.0},
        {"name": "B", "spend": 600, "roas": 1.0, "purchases": 3, "frequency": 2.0},
        {"name": "C", "spend": 700, "roas": 6.0, "purchases": 10, "frequency": 2.0},
    ]
    contributors = diagnose_contributors(rows, account_roas=5.0)
    names = {c["name"] for c in contributors}
    assert "A" in names  # satışsız harcama
    assert "B" in names  # hesap ortalamasının çok altında
    assert "C" not in names  # sağlıklı
