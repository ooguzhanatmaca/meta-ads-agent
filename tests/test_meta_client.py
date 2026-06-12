from unittest.mock import Mock, patch

import pytest
import requests

from app.meta.client import (
    AD_ACCOUNT_FIELDS,
    ACCOUNT_INSIGHT_FIELDS,
    MetaClient,
    MetaConfigurationError,
    MetaRequestError,
    MetaResponseError,
)


def build_client(ad_account_id: str = "123456") -> MetaClient:
    return MetaClient(
        access_token="test-token",
        ad_account_id=ad_account_id,
        graph_api_version="v23.0",
    )


def test_normalizes_ad_account_id() -> None:
    assert build_client().ad_account_id == "act_123456"
    assert build_client("act_123456").ad_account_id == "act_123456"


@patch("app.meta.client.requests.get")
def test_get_ad_account_info_requests_expected_fields(mock_get: Mock) -> None:
    expected_payload = {
        "id": "act_123456",
        "name": "Test Account",
        "account_status": 1,
        "currency": "TRY",
        "timezone_name": "Europe/Istanbul",
        "amount_spent": "1000",
    }
    mock_get.return_value = Mock(ok=True)
    mock_get.return_value.json.return_value = expected_payload

    result = build_client().get_ad_account_info()

    assert result == expected_payload
    mock_get.assert_called_once_with(
        "https://graph.facebook.com/v23.0/act_123456",
        headers={"Authorization": "Bearer test-token"},
        params={"fields": ",".join(AD_ACCOUNT_FIELDS)},
        timeout=15,
    )


@patch("app.meta.client.requests.get")
def test_timeout_is_converted_to_safe_error(mock_get: Mock) -> None:
    mock_get.side_effect = requests.Timeout("test-token")

    with pytest.raises(MetaRequestError, match="zaman aşımına") as error_info:
        build_client().get_ad_account_info()

    assert "test-token" not in str(error_info.value)


@patch("app.meta.client.requests.get")
def test_meta_error_is_converted_and_token_is_redacted(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=False, status_code=400)
    mock_get.return_value.json.return_value = {
        "error": {"message": "Invalid token test-token", "code": 190}
    }

    with pytest.raises(MetaResponseError) as error_info:
        build_client().get_ad_account_info()

    message = str(error_info.value)
    assert "HTTP 400" in message
    assert "kod: 190" in message
    assert "test-token" not in message


def test_missing_configuration_is_rejected() -> None:
    with pytest.raises(MetaConfigurationError, match="META_ACCESS_TOKEN"):
        MetaClient("", "123456", "v23.0")


@patch.object(MetaClient, "get_ad_account_info", return_value={"id": "act_123456"})
def test_connection_returns_true(mock_get_ad_account_info: Mock) -> None:
    assert build_client().test_connection() is True
    mock_get_ad_account_info.assert_called_once_with()


@patch("app.meta.client.requests.get")
def test_get_account_insights_requests_last_seven_days(mock_get: Mock) -> None:
    expected_insight = {"spend": "100", "impressions": "5000"}
    mock_get.return_value = Mock(ok=True)
    mock_get.return_value.json.return_value = {"data": [expected_insight]}

    result = build_client().get_account_insights()

    assert result == expected_insight
    mock_get.assert_called_once_with(
        "https://graph.facebook.com/v23.0/act_123456/insights",
        headers={"Authorization": "Bearer test-token"},
        params={
            "fields": ",".join(ACCOUNT_INSIGHT_FIELDS),
            "date_preset": "last_7d",
            "level": "account",
        },
        timeout=15,
    )


@patch("app.meta.client.requests.get")
def test_get_account_insights_handles_empty_data(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=True)
    mock_get.return_value.json.return_value = {"data": []}

    assert build_client().get_account_insights() == {}


@patch("app.meta.client.requests.get")
def test_get_account_insights_for_explicit_period(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=True)
    mock_get.return_value.json.return_value = {"data": [{"spend": "25"}]}

    result = build_client().get_account_insights_for_period(
        "2026-06-01", "2026-06-03"
    )

    assert result == {"spend": "25"}
    params = mock_get.call_args.kwargs["params"]
    assert params["time_range"] == '{"since": "2026-06-01", "until": "2026-06-03"}'
    assert params["level"] == "account"
    assert "access_token" not in str(mock_get.call_args)


@patch("app.meta.client.requests.get")
def test_get_performance_report_uses_entity_edge_and_pagination(mock_get: Mock) -> None:
    mock_get.side_effect = [
        Mock(
            ok=True,
            **{
                "json.return_value": {
                    "data": [{"id": "1"}],
                    "paging": {
                        "cursors": {"after": "cursor-1"},
                        "next": "https://example.invalid/next",
                    },
                }
            },
        ),
        Mock(ok=True, **{"json.return_value": {"data": [{"id": "2"}]}}),
    ]

    result = build_client().get_performance_report("campaign")

    assert result == [{"id": "1"}, {"id": "2"}]
    first_params = mock_get.call_args_list[0].kwargs["params"]
    second_params = mock_get.call_args_list[1].kwargs["params"]
    assert "id,name,status,insights.date_preset(last_7d)" in first_params["fields"]
    assert first_params["limit"] == "100"
    assert second_params["after"] == "cursor-1"
    assert "access_token" not in str(mock_get.call_args_list)


@patch("app.meta.client.requests.get")
def test_get_performance_report_for_explicit_period(mock_get: Mock) -> None:
    mock_get.return_value = Mock(ok=True)
    mock_get.return_value.json.return_value = {"data": []}

    result = build_client().get_performance_report_for_period(
        "ad",
        "2026-06-01",
        "2026-06-07",
    )

    assert result == []
    fields = mock_get.call_args.kwargs["params"]["fields"]
    assert "adset{id,name}" in fields
    assert "campaign{id,name}" in fields
    assert "creative{id,name,thumbnail_url,object_type,video_id,image_url}" in fields
    assert "video_play_actions" in fields
    assert "video_thruplay_watched_actions" in fields
    assert (
        'insights.time_range({"since":"2026-06-01","until":"2026-06-07"})'
        in fields
    )
    assert "access_token" not in str(mock_get.call_args)


def test_get_performance_report_rejects_unknown_level() -> None:
    with pytest.raises(MetaConfigurationError, match="Desteklenmeyen"):
        build_client().get_performance_report("unknown")
