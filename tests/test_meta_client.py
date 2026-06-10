from unittest.mock import Mock, patch

import pytest
import requests

from app.meta.client import (
    AD_ACCOUNT_FIELDS,
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
