from datetime import date
from unittest.mock import patch

from app.meta.compare_periods import build_default_periods
from app.meta.executive_summary import (
    filter_recommendations,
    format_ad_list,
    main,
    select_best_ads,
    select_worst_ads,
)


def ad(name: str, spend: float, roas: float, purchases: float = 0):
    return {
        "name": name,
        "spend": spend,
        "purchases": purchases,
        "cpa": spend / purchases if purchases else 0,
        "roas": roas,
        "frequency": 2,
    }


def test_selects_best_and_worst_ads_deterministically() -> None:
    ads = [
        ad("Strong", 1000, 5, 10),
        ad("Weak high spend", 2000, 0),
        ad("Weak low spend", 500, 0),
        ad("Middle", 800, 2, 2),
    ]

    assert select_best_ads(ads, 2)[0]["name"] == "Strong"
    assert [item["name"] for item in select_worst_ads(ads, 2)] == [
        "Weak high spend",
        "Weak low spend",
    ]


def test_filter_recommendations_uses_existing_rule_labels() -> None:
    recommendations = [
        {"recommendation": "Kapatılmaya aday"},
        {"recommendation": "Kreatif değiştir"},
    ]

    assert filter_recommendations(recommendations, "Kreatif değiştir") == [
        {"recommendation": "Kreatif değiştir"}
    ]


def test_format_ad_list_handles_empty_and_zero_values() -> None:
    assert "Kayıt bulunamadı" in format_ad_list("Test", [])
    assert "Zero" in format_ad_list("Test", [ad("Zero", 0, 0)])


@patch("app.meta.executive_summary.build_default_periods")
@patch("app.meta.executive_summary.get_performance_report")
@patch("app.meta.executive_summary.get_account_insights_for_period")
def test_cli_builds_all_sections_with_mocked_data(
    mock_insights, mock_report, mock_periods, capsys
) -> None:
    periods = build_default_periods(date(2026, 6, 11))
    mock_periods.return_value = periods
    mock_insights.side_effect = [
        {"spend": "100", "impressions": "1000", "reach": "500"},
        {"spend": "80", "impressions": "800", "reach": "400"},
        {"spend": "1000", "impressions": "10000", "reach": "5000"},
        {"spend": "900", "impressions": "9000", "reach": "4500"},
    ]
    mock_report.return_value = [
        {
            "id": "1",
            "name": "Critical Ad",
            "insights": {"data": [{"spend": "1600"}]},
        },
        {
            "id": "2",
            "name": "Scale Ad",
            "insights": {
                "data": [
                    {
                        "spend": "1000",
                        "impressions": "10000",
                        "reach": "5000",
                        "clicks": "100",
                        "actions": [{"action_type": "purchase", "value": "5"}],
                        "action_values": [
                            {"action_type": "purchase", "value": "5000"}
                        ],
                    }
                ]
            },
        },
        {
            "id": "3",
            "name": "Tired Ad",
            "insights": {
                "data": [
                    {
                        "spend": "600",
                        "impressions": "4000",
                        "reach": "1000",
                        "clicks": "20",
                    }
                ]
            },
        },
    ]

    assert main() == 0

    output = capsys.readouterr().out
    for heading in (
        "Bugünkü hesap özeti",
        "Bugün vs dün",
        "Son 7 gün vs önceki 7 gün",
        "En iyi 5 reklam",
        "En kötü 5 reklam",
        "Kapatılmaya aday reklamlar",
        "Bütçe artırılmaya aday reklamlar",
        "Kreatif yorgunluğu olan reklamlar",
        "Öncelik sırasına göre aksiyon listesi",
    ):
        assert heading in output
    assert "Critical Ad" in output
    assert "Scale Ad" in output
    assert "Tired Ad" in output
    assert "test-token" not in output
    assert mock_insights.call_count == 4
    mock_report.assert_called_once_with("ad", "last_7d")
