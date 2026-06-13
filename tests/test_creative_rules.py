from app.rules.creative_rules import (
    build_creative_brief,
    creative_health,
    evaluate_creative,
    evaluate_creatives,
)


def test_creative_without_purchases_is_marked_as_not_working() -> None:
    result = evaluate_creative(
        {"name": "Ad", "spend": 1200, "purchases": 0, "creative_type": "Görsel"}
    )

    assert result["creative_label"] == "Bu kreatif çalışmıyor"
    assert result["creative_priority"] == "critical"


def test_winning_video_gets_video_variation_recommendation() -> None:
    result = evaluate_creative(
        {
            "name": "Winner",
            "spend": 800,
            "purchases": 8,
            "roas": 5,
            "frequency": 2,
            "creative_type": "Video",
            "video_plays": 100,
            "video_hook_rate": 10,
        }
    )

    assert result["creative_label"] == "Bu kreatif tuttu"
    assert "hook" in result["creative_recommendation"]


def test_video_with_low_start_rate_recommends_new_first_seconds() -> None:
    result = evaluate_creative(
        {
            "name": "Slow Video",
            "spend": 600,
            "purchases": 1,
            "creative_type": "Video",
            "video_plays": 100,
            "video_hook_rate": 10,
        }
    )

    assert result["creative_label"] == "Video açılışı zayıf"
    assert "İlk 3 saniyeyi" in result["creative_recommendation"]


def test_creatives_are_sorted_by_priority_then_spend() -> None:
    results = evaluate_creatives(
        [
            {"name": "Low", "spend": 100, "creative_type": "Görsel"},
            {"name": "Critical", "spend": 1500, "purchases": 0},
        ]
    )

    assert results[0]["name"] == "Critical"


def test_creative_health_is_bounded_and_classified() -> None:
    score, status = creative_health(
        {"spend": 1000, "purchases": 8, "roas": 5, "ctr": 2.2, "frequency": 2}
    )

    assert score == 100
    assert status == "Sağlıklı"


def test_video_brief_is_created_without_external_calls() -> None:
    brief = build_creative_brief(
        {"creative_type": "Video", "video_hook_rate": 10, "roas": 3, "ctr": 1}
    )

    assert "İlk karede" in brief["hook"]
    assert brief["cta"] == "Şimdi incele"
