from app.rules.opportunity_rules import (
    best_segment,
    reallocation_candidates,
    scaling_candidate,
    underspending_winner,
)


def test_best_segment_picks_highest_roas_above_average() -> None:
    rows = [
        {"label": "18-24", "roas": 3.0, "spend": 1000},
        {"label": "25-34", "roas": 7.0, "spend": 1000},
        {"label": "35-44", "roas": 2.0, "spend": 1000},
    ]
    seg = best_segment(rows, account_roas=4.0)
    assert seg["label"] == "25-34"


def test_best_segment_respects_min_spend() -> None:
    rows = [{"label": "55-64", "roas": 9.0, "spend": 50}]
    assert best_segment(rows, account_roas=4.0, min_spend=300) is None


def test_underspending_winner_flags_high_roas_low_share() -> None:
    rows = [
        {"label": "A", "roas": 9.0, "spend": 200},   # yüksek ROAS, düşük pay
        {"label": "B", "roas": 4.0, "spend": 3000},
    ]
    seg = underspending_winner(rows, account_roas=4.0)
    assert seg["label"] == "A"


def test_reallocation_finds_up_and_down() -> None:
    campaigns = [
        {"name": "Iyi", "roas": 6.0, "purchases": 10, "frequency": 2.0, "spend": 1000},
        {"name": "Kotu", "roas": 1.5, "purchases": 5, "frequency": 2.0, "spend": 2000},
    ]
    up, down = reallocation_candidates(campaigns, account_roas=4.0)
    assert up and up[0]["name"] == "Iyi"
    assert down and down[0]["name"] == "Kotu"


def test_scaling_candidate_requires_healthy_metrics() -> None:
    adsets = [
        {"name": "Yorgun", "roas": 5.0, "purchases": 10, "frequency": 4.0},  # freq yüksek
        {"name": "Kazanan", "roas": 6.0, "purchases": 8, "frequency": 2.0},
    ]
    candidate = scaling_candidate(adsets)
    assert candidate["name"] == "Kazanan"


def test_scaling_candidate_none_when_no_winner() -> None:
    adsets = [{"name": "Zayif", "roas": 1.5, "purchases": 1, "frequency": 2.0}]
    assert scaling_candidate(adsets) is None
