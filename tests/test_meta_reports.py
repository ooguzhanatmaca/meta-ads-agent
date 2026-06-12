from unittest.mock import patch

import pytest

from app.meta.ad_report import main as ad_main
from app.meta.adset_report import main as adset_main
from app.meta.campaign_report import main as campaign_main
from app.meta.performance_report import calculate_report_rows, format_report


def test_report_rows_calculate_metrics_and_sort_by_spend() -> None:
    entities = [
        {
            "id": "1",
            "name": "Low spend",
            "status": "PAUSED",
            "insights": {"data": [{"spend": "10"}]},
        },
        {
            "id": "2",
            "name": "High spend",
            "status": "ACTIVE",
            "insights": {
                "data": [
                    {
                        "spend": "200",
                        "impressions": "10000",
                        "reach": "5000",
                        "clicks": "100",
                        "actions": [
                            {
                                "action_type": "offsite_conversion.fb_pixel_purchase",
                                "value": "4",
                            }
                        ],
                        "action_values": [
                            {"action_type": "omni_purchase", "value": "600"}
                        ],
                    }
                ]
            },
        },
    ]

    rows = calculate_report_rows(entities)

    assert [row["id"] for row in rows] == ["2", "1"]
    expected_metrics = {
        "spend": 200,
        "impressions": 10000,
        "reach": 5000,
        "clicks": 100,
        "ctr": 1,
        "cpc": 2,
        "cpm": 20,
        "purchases": 4,
        "purchase_value": 600,
        "cpa": 50,
        "roas": 3,
        "frequency": 2,
    }
    actual_metrics = {key: rows[0][key] for key in expected_metrics}
    assert actual_metrics == pytest.approx(expected_metrics, abs=0.001)


def test_report_rows_handle_missing_and_zero_values() -> None:
    row = calculate_report_rows([{"id": "1", "name": "Empty"}])[0]

    assert row["frequency"] == 0
    assert row["cpa"] == 0
    assert row["roas"] == 0


def test_report_rows_include_parent_names() -> None:
    row = calculate_report_rows(
        [
            {
                "id": "1",
                "name": "Ad",
                "campaign": {"name": "Campaign"},
                "adset": {"name": "Ad Set"},
            }
        ]
    )[0]

    assert row["campaign_name"] == "Campaign"
    assert row["adset_name"] == "Ad Set"


def test_report_rows_include_creative_and_video_metrics() -> None:
    row = calculate_report_rows(
        [
            {
                "id": "1",
                "name": "Video Ad",
                "creative": {
                    "id": "creative-1",
                    "name": "Video Creative",
                    "thumbnail_url": "https://example.invalid/video.jpg",
                    "object_type": "VIDEO",
                    "video_id": "video-1",
                },
                "insights": {
                    "data": [
                        {
                            "impressions": "1000",
                            "video_play_actions": [{"value": "400"}],
                            "video_p75_watched_actions": [{"value": "100"}],
                            "video_thruplay_watched_actions": [{"value": "80"}],
                        }
                    ]
                },
            }
        ]
    )[0]

    assert row["creative_id"] == "creative-1"
    assert row["creative_type"] == "Video"
    assert row["video_hook_rate"] == 40
    assert row["video_hold_rate"] == 25
    assert row["video_thruplays"] == 80


def test_format_report_contains_readable_table() -> None:
    output = format_report("Test raporu", calculate_report_rows([{"id": "1", "name": "Test"}]))

    assert "Test raporu - son 7 gün" in output
    assert "Harcama" in output
    assert "ROAS" in output


@pytest.mark.parametrize(
    ("main", "level"),
    ((campaign_main, "campaign"), (adset_main, "adset"), (ad_main, "ad")),
)
@patch("app.meta.performance_report.get_performance_report")
def test_report_clis_use_mocked_meta_data(mock_get, main, level, capsys) -> None:
    mock_get.return_value = []

    assert main() == 0
    assert "Kayıt bulunamadı" in capsys.readouterr().out
    mock_get.assert_called_once_with(level, "last_7d")
