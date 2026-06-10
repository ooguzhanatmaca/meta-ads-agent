from unittest.mock import patch

import pytest

from app.meta.recommendations import format_recommendations, main
from app.rules.performance_rules import evaluate_ad, evaluate_ads


def ad(**overrides):
    values = {
        "name": "Test Ad",
        "spend": 600,
        "purchases": 1,
        "cpa": 600,
        "roas": 2,
        "frequency": 2,
        "ctr": 1.5,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("metrics", "expected", "priority"),
    (
        ({"spend": 1000, "purchases": 0}, "Kapatılmaya aday", "critical"),
        (
            {"spend": 1500, "roas": 1.49},
            "Bütçeyi azalt veya reklamı kapat",
            "high",
        ),
        ({"cpa": 501, "purchases": 2}, "CPA yüksek", "high"),
        ({"frequency": 3.5, "ctr": 0.99}, "Kreatif değiştir", "medium"),
        (
            {"roas": 4, "purchases": 5, "frequency": 3.49},
            "Bütçeyi kontrollü artır",
            "medium",
        ),
        ({"spend": 499}, "Yetersiz veri, izlemeye devam et", "low"),
        ({"roas": 2.5, "cpa": 400}, "İyi performans", "low"),
    ),
)
def test_each_rule_matches(metrics, expected, priority) -> None:
    recommendations = evaluate_ad(ad(**metrics))

    match = next(item for item in recommendations if item["recommendation"] == expected)
    assert match["priority"] == priority
    assert match["reason"]


def test_one_ad_can_have_multiple_recommendations() -> None:
    recommendations = evaluate_ad(ad(spend=1600, purchases=0, roas=0))
    labels = {item["recommendation"] for item in recommendations}

    assert "Kapatılmaya aday" in labels
    assert "Bütçeyi azalt veya reklamı kapat" in labels


def test_recommendations_sort_by_priority_then_spend() -> None:
    recommendations = evaluate_ads(
        [
            ad(name="Lower critical", spend=1000, purchases=0),
            ad(name="Higher critical", spend=2000, purchases=0),
            ad(name="Medium", frequency=4, ctr=0.5),
        ]
    )

    critical_names = [
        item["name"] for item in recommendations if item["priority"] == "critical"
    ]
    assert critical_names == ["Higher critical", "Lower critical"]
    priorities = [item["priority"] for item in recommendations]
    assert priorities == sorted(
        priorities, key={"critical": 0, "high": 1, "medium": 2, "low": 3}.get
    )


def test_format_recommendations_contains_requested_fields() -> None:
    output = format_recommendations(evaluate_ad(ad(spend=1000, purchases=0)))

    for heading in ("Reklam", "Harcama", "Satın Alma", "CPA", "ROAS", "Frekans", "Öneri", "Gerekçe"):
        assert heading in output


@patch("app.meta.recommendations.get_performance_report")
def test_recommendations_cli_reuses_ad_report_data(mock_get, capsys) -> None:
    mock_get.return_value = [
        {
            "id": "1",
            "name": "Mock Ad",
            "insights": {"data": [{"spend": "1000"}]},
        }
    ]

    assert main() == 0
    output = capsys.readouterr().out
    assert "Mock Ad" in output
    assert "Kapatılmaya aday" in output
    assert "test-token" not in output
    mock_get.assert_called_once_with("ad", "last_7d")
