"""CLI for testing the configured Meta ad account connection."""

from typing import Any

from app.meta.client import MetaAPIError, get_ad_account_info


def format_account_info(account: dict[str, Any]) -> str:
    """Format safe account details for terminal output."""
    return "\n".join(
        (
            "Meta bağlantısı başarılı.",
            f"Hesap adı: {account.get('name') or '-'}",
            f"Hesap ID: {account.get('id') or '-'}",
            f"Durum: {account.get('account_status') or '-'}",
            f"Para birimi: {account.get('currency') or '-'}",
            f"Saat dilimi: {account.get('timezone_name') or '-'}",
        )
    )


def main() -> int:
    try:
        print(format_account_info(get_ad_account_info()))
    except MetaAPIError as error:
        print(f"Meta bağlantısı başarısız: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
