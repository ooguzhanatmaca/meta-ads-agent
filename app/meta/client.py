"""Read-only client for the Meta Marketing API."""

import json
import os
from typing import Any

import requests
from dotenv import load_dotenv


AD_ACCOUNT_FIELDS = (
    "id",
    "name",
    "account_status",
    "currency",
    "timezone_name",
    "amount_spent",
)
ACCOUNT_INSIGHT_FIELDS = (
    "spend",
    "impressions",
    "reach",
    "clicks",
    "actions",
    "action_values",
    "video_play_actions",
    "video_p25_watched_actions",
    "video_p50_watched_actions",
    "video_p75_watched_actions",
    "video_p95_watched_actions",
    "video_thruplay_watched_actions",
)
REPORT_LEVEL_EDGES = {
    "campaign": "campaigns",
    "adset": "adsets",
    "ad": "ads",
}
REPORT_LEVEL_FIELDS = {
    "campaign": "id,name,status",
    "adset": "id,name,campaign{id,name},status",
    "ad": (
        "id,name,adset{id,name},campaign{id,name},status,"
        "creative{id,name,thumbnail_url,object_type,video_id,image_url}"
    ),
}
DEFAULT_TIMEOUT_SECONDS = 15


class MetaAPIError(RuntimeError):
    """Base error for Meta API operations."""


class MetaConfigurationError(MetaAPIError):
    """Raised when required Meta configuration is missing or invalid."""


class MetaRequestError(MetaAPIError):
    """Raised when the Meta API request cannot be completed."""


class MetaResponseError(MetaAPIError):
    """Raised when Meta returns an error or an invalid response."""


class MetaClient:
    """Minimal read-only client for a configured Meta ad account."""

    def __init__(
        self,
        access_token: str,
        ad_account_id: str,
        graph_api_version: str,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not access_token:
            raise MetaConfigurationError("META_ACCESS_TOKEN tanımlı değil.")
        if not ad_account_id:
            raise MetaConfigurationError("META_AD_ACCOUNT_ID tanımlı değil.")
        if not graph_api_version:
            raise MetaConfigurationError("META_GRAPH_API_VERSION tanımlı değil.")

        self._access_token = access_token
        self.ad_account_id = self._normalize_ad_account_id(ad_account_id)
        self.graph_api_version = graph_api_version.strip().strip("/")
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "MetaClient":
        """Create a client from values loaded through the local environment."""
        load_dotenv()
        return cls(
            access_token=os.getenv("META_ACCESS_TOKEN", "").strip(),
            ad_account_id=os.getenv("META_AD_ACCOUNT_ID", "").strip(),
            graph_api_version=os.getenv("META_GRAPH_API_VERSION", "").strip(),
        )

    @staticmethod
    def _normalize_ad_account_id(ad_account_id: str) -> str:
        normalized_id = ad_account_id.strip()
        if not normalized_id.startswith("act_"):
            normalized_id = f"act_{normalized_id}"
        return normalized_id

    def get_ad_account_info(self) -> dict[str, Any]:
        """Return basic information for the configured ad account."""
        url = (
            f"https://graph.facebook.com/{self.graph_api_version}/"
            f"{self.ad_account_id}"
        )

        return self._get(url, {"fields": ",".join(AD_ACCOUNT_FIELDS)})

    def get_account_insights(self, date_preset: str = "last_7d") -> dict[str, Any]:
        """Return account-level performance metrics for a read-only date preset."""
        return self._get_account_insights({"date_preset": date_preset})

    def get_account_insights_for_period(
        self, since: str, until: str
    ) -> dict[str, Any]:
        """Return account-level metrics for an explicit inclusive date range."""
        return self._get_account_insights(
            {"time_range": json.dumps({"since": since, "until": until})}
        )

    def get_account_insights_breakdown(
        self, breakdowns: str, date_preset: str = "last_7d"
    ) -> list[dict[str, Any]]:
        """Return account insights split by a breakdown (e.g. age, gender, placement)."""
        url = (
            f"https://graph.facebook.com/{self.graph_api_version}/"
            f"{self.ad_account_id}/insights"
        )
        payload = self._get(
            url,
            {
                "fields": ",".join(ACCOUNT_INSIGHT_FIELDS),
                "level": "account",
                "breakdowns": breakdowns,
                "date_preset": date_preset,
                "limit": "200",
            },
        )
        data = payload.get("data")
        if not isinstance(data, list) or not all(
            isinstance(item, dict) for item in data
        ):
            raise MetaResponseError("Meta API kırılım verisi beklenen biçimde değil.")
        return data

    def _get_account_insights(self, period_params: dict[str, str]) -> dict[str, Any]:
        url = (
            f"https://graph.facebook.com/{self.graph_api_version}/"
            f"{self.ad_account_id}/insights"
        )
        payload = self._get(
            url,
            {
                "fields": ",".join(ACCOUNT_INSIGHT_FIELDS),
                "level": "account",
                **period_params,
            },
        )
        data = payload.get("data")
        if not isinstance(data, list):
            raise MetaResponseError("Meta API insights verisi beklenen biçimde değil.")

        insight = data[0] if data else {}
        if not isinstance(insight, dict):
            raise MetaResponseError("Meta API insights satırı beklenen biçimde değil.")
        return insight

    def get_performance_report(
        self, level: str, date_preset: str = "last_7d"
    ) -> list[dict[str, Any]]:
        """Return read-only entity details with nested performance insights."""
        insight_period = f"date_preset({date_preset})"
        return self._get_performance_report(level, insight_period)

    def get_performance_report_for_period(
        self, level: str, since: str, until: str
    ) -> list[dict[str, Any]]:
        """Return entity performance for an explicit inclusive date range."""
        time_range = json.dumps(
            {"since": since, "until": until},
            separators=(",", ":"),
        )
        return self._get_performance_report(level, f"time_range({time_range})")

    def get_account_daily_insights(
        self, since: str, until: str
    ) -> list[dict[str, Any]]:
        """Return account-level daily insight rows (one per day) for a range."""
        url = (
            f"https://graph.facebook.com/{self.graph_api_version}/"
            f"{self.ad_account_id}/insights"
        )
        params = {
            "fields": "date_start,date_stop," + ",".join(ACCOUNT_INSIGHT_FIELDS),
            "level": "account",
            "time_increment": "1",
            "time_range": json.dumps(
                {"since": since, "until": until},
                separators=(",", ":"),
            ),
            "limit": "500",
        }
        rows: list[dict[str, Any]] = []
        while True:
            payload = self._get(url, params)
            data = payload.get("data")
            if not isinstance(data, list) or not all(
                isinstance(item, dict) for item in data
            ):
                raise MetaResponseError(
                    "Meta API günlük hesap verisi beklenen biçimde değil."
                )
            rows.extend(data)
            paging = payload.get("paging")
            cursors = paging.get("cursors") if isinstance(paging, dict) else None
            after = cursors.get("after") if isinstance(cursors, dict) else None
            if not after or not paging.get("next"):
                break
            params = {**params, "after": str(after)}
        return rows

    def get_ad_daily_insights_for_period(
        self, since: str, until: str
    ) -> list[dict[str, Any]]:
        """Return daily ad insights for trend charts without write operations."""
        url = (
            f"https://graph.facebook.com/{self.graph_api_version}/"
            f"{self.ad_account_id}/insights"
        )
        params = {
            "fields": (
                "ad_id,ad_name,date_start,date_stop,"
                + ",".join(ACCOUNT_INSIGHT_FIELDS)
            ),
            "level": "ad",
            "time_increment": "1",
            "time_range": json.dumps(
                {"since": since, "until": until},
                separators=(",", ":"),
            ),
            "limit": "500",
        }
        rows: list[dict[str, Any]] = []
        while True:
            payload = self._get(url, params)
            data = payload.get("data")
            if not isinstance(data, list) or not all(
                isinstance(item, dict) for item in data
            ):
                raise MetaResponseError(
                    "Meta API günlük reklam verisi beklenen biçimde değil."
                )
            rows.extend(data)
            paging = payload.get("paging")
            cursors = paging.get("cursors") if isinstance(paging, dict) else None
            after = cursors.get("after") if isinstance(cursors, dict) else None
            if not after or not paging.get("next"):
                break
            params = {**params, "after": str(after)}
        return rows

    def _get_performance_report(
        self, level: str, insight_period: str
    ) -> list[dict[str, Any]]:
        edge = REPORT_LEVEL_EDGES.get(level)
        if edge is None:
            raise MetaConfigurationError(f"Desteklenmeyen rapor seviyesi: {level}")

        url = (
            f"https://graph.facebook.com/{self.graph_api_version}/"
            f"{self.ad_account_id}/{edge}"
        )
        insight_fields = ",".join(ACCOUNT_INSIGHT_FIELDS)
        entity_fields = REPORT_LEVEL_FIELDS[level]
        params = {
            "fields": (
                f"{entity_fields},"
                f"insights.{insight_period}{{{insight_fields}}}"
            ),
            "limit": "100",
        }

        entities: list[dict[str, Any]] = []
        while True:
            payload = self._get(url, params)
            data = payload.get("data")
            if not isinstance(data, list):
                raise MetaResponseError("Meta API rapor verisi beklenen biçimde değil.")
            if not all(isinstance(item, dict) for item in data):
                raise MetaResponseError("Meta API rapor satırı beklenen biçimde değil.")
            entities.extend(data)

            paging = payload.get("paging")
            cursors = paging.get("cursors") if isinstance(paging, dict) else None
            after = cursors.get("after") if isinstance(cursors, dict) else None
            if not after or not paging.get("next"):
                break
            params = {**params, "after": str(after)}

        return entities

    def _get(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        """Send an authenticated GET request without exposing credentials."""

        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                params=params,
                timeout=self.timeout,
            )
        except requests.Timeout as error:
            raise MetaRequestError("Meta API isteği zaman aşımına uğradı.") from error
        except requests.RequestException as error:
            raise MetaRequestError("Meta API bağlantısı kurulamadı.") from error

        try:
            payload = response.json()
        except requests.exceptions.JSONDecodeError as error:
            raise MetaResponseError("Meta API geçersiz bir yanıt döndürdü.") from error

        if not response.ok:
            raise self._response_error(response.status_code, payload)
        if not isinstance(payload, dict):
            raise MetaResponseError("Meta API beklenmeyen bir yanıt döndürdü.")

        return payload

    def test_connection(self) -> bool:
        """Verify that the configured account can be read."""
        self.get_ad_account_info()
        return True

    def _response_error(self, status_code: int, payload: Any) -> MetaResponseError:
        message = "Bilinmeyen Meta API hatası"
        error_code = None

        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            error_data = payload["error"]
            message = str(error_data.get("message") or message)
            error_code = error_data.get("code")

        message = message.replace(self._access_token, "[GİZLENDİ]")
        code_text = f", kod: {error_code}" if error_code is not None else ""
        return MetaResponseError(
            f"Meta API isteği başarısız oldu (HTTP {status_code}{code_text}): {message}"
        )


def get_ad_account_info() -> dict[str, Any]:
    """Read basic information for the configured Meta ad account."""
    return MetaClient.from_env().get_ad_account_info()


def test_meta_connection() -> bool:
    """Test access to the configured Meta ad account."""
    return MetaClient.from_env().test_connection()


def get_account_insights(date_preset: str = "last_7d") -> dict[str, Any]:
    """Read account-level insights for the configured Meta ad account."""
    return MetaClient.from_env().get_account_insights(date_preset)


def get_account_insights_for_period(since: str, until: str) -> dict[str, Any]:
    """Read account insights for an explicit inclusive date range."""
    return MetaClient.from_env().get_account_insights_for_period(since, until)


def get_account_insights_breakdown(
    breakdowns: str, date_preset: str = "last_7d"
) -> list[dict[str, Any]]:
    """Read account insights split by a breakdown for the configured account."""
    return MetaClient.from_env().get_account_insights_breakdown(
        breakdowns, date_preset
    )


def get_performance_report(
    level: str, date_preset: str = "last_7d"
) -> list[dict[str, Any]]:
    """Read entity-level performance for the configured Meta ad account."""
    return MetaClient.from_env().get_performance_report(level, date_preset)


def get_performance_report_for_period(
    level: str, since: str, until: str
) -> list[dict[str, Any]]:
    """Read entity performance for an explicit inclusive date range."""
    return MetaClient.from_env().get_performance_report_for_period(
        level, since, until
    )


def get_ad_daily_insights_for_period(
    since: str, until: str
) -> list[dict[str, Any]]:
    return MetaClient.from_env().get_ad_daily_insights_for_period(since, until)


def get_account_daily_insights(since: str, until: str) -> list[dict[str, Any]]:
    """Read account-level daily insight rows for the configured account."""
    return MetaClient.from_env().get_account_daily_insights(since, until)
