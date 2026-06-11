"""Meta Marketing API integration."""

from app.meta.client import (
    MetaAPIError,
    MetaClient,
    MetaConfigurationError,
    MetaRequestError,
    MetaResponseError,
    get_account_insights,
    get_account_insights_for_period,
    get_ad_account_info,
    get_performance_report,
    get_performance_report_for_period,
    test_meta_connection,
)

__all__ = [
    "MetaAPIError",
    "MetaClient",
    "MetaConfigurationError",
    "MetaRequestError",
    "MetaResponseError",
    "get_account_insights",
    "get_account_insights_for_period",
    "get_ad_account_info",
    "get_performance_report",
    "get_performance_report_for_period",
    "test_meta_connection",
]
