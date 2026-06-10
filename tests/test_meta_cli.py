from unittest.mock import patch

import pytest

from app.meta.account_summary import calculate_summary, main as summary_main
from app.meta.client import MetaResponseError
from app.meta.test_connection import main as connection_main


@patch("app.meta.test_connection.get_ad_account_info")
def test_connection_cli_prints_account_without_token(mock_get, capsys) -> None:
    mock_get.return_value = {
        "name": "Test Account",
        "id": "act_123",
        "account_status": 1,
        "currency": "TRY",
        "timezone_name": "Europe/Istanbul",
    }

    assert connection_main() == 0

    output = capsys.readouterr().out
    assert "Test Account" in output
    assert "act_123" in output
    assert "test-token" not in output


def test_calculate_summary_parses_purchase_values() -> None:
    summary = calculate_summary(
        {
            "spend": "200",
            "impressions": "10000",
            "reach": "8000",
            "clicks": "100",
            "actions": [
                {"action_type": "link_click", "value": "90"},
                {"action_type": "purchase", "value": "4"},
                {"action_type": "omni_purchase", "value": "5"},
            ],
            "action_values": [
                {"action_type": "purchase", "value": "600"},
                {"action_type": "omni_purchase", "value": "700"},
            ],
        }
    )

    assert summary == pytest.approx(
        {
            "spend": 200,
            "impressions": 10000,
            "reach": 8000,
            "clicks": 100,
            "ctr": 1,
            "cpc": 2,
            "cpm": 20,
            "purchases": 4,
            "purchase_value": 600,
            "cpa": 50,
            "roas": 3,
        }
    )


def test_calculate_summary_handles_missing_and_zero_values() -> None:
    summary = calculate_summary({})

    assert all(value == 0 for value in summary.values())


@patch("app.meta.account_summary.get_account_insights")
def test_summary_cli_uses_mocked_insights(mock_get, capsys) -> None:
    mock_get.return_value = {"spend": "0", "impressions": "0"}

    assert summary_main() == 0
    assert "son 7 gün" in capsys.readouterr().out
    mock_get.assert_called_once_with("last_7d")


@patch("app.meta.test_connection.get_ad_account_info")
def test_connection_cli_returns_error_without_exposing_token(mock_get, capsys) -> None:
    mock_get.side_effect = MetaResponseError("Güvenli hata")

    assert connection_main() == 1
    output = capsys.readouterr().out
    assert "Güvenli hata" in output
    assert "test-token" not in output
