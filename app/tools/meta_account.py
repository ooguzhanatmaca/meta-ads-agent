"""Read-only Meta account tools for the OpenAI Agents SDK."""

from typing import Any

from agents import function_tool

from app.meta.client import get_ad_account_info


@function_tool
def get_meta_ad_account_info() -> dict[str, Any]:
    """Get basic, read-only information for the configured Meta ad account."""
    return get_ad_account_info()
