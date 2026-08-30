from pathlib import Path

from app.services.accounts import AccountRegistry, BrokerAccountProfile


def account(account_id: str, login: str, account_type: str) -> BrokerAccountProfile:
    return BrokerAccountProfile(
        id=account_id,
        provider="JustMarkets",
        login=login,
        server="JustMarkets-Live",
        account_type=account_type,
        terminal_path=r"C:\Program Files\JustMarkets MetaTrader 5\terminal64.exe",
    )


def test_registry_masks_logins_and_persists_active_account(tmp_path: Path) -> None:
    path = tmp_path / "accounts.json"
    registry = AccountRegistry(
        path,
        [
            account("standard-account", "1000000002", "Standard"),
            account("pro-account", "1000000236", "Pro"),
        ],
    )

    active_account = registry.active_account()
    assert active_account is not None
    assert active_account.login_masked == "******0002"
    registry.set_active("pro-account")

    reloaded = AccountRegistry(path)
    reloaded_account = reloaded.active_account()
    assert reloaded.active_account_id == "pro-account"
    assert reloaded_account is not None
    assert reloaded_account.login_masked == "******0236"


def test_switching_account_does_not_verify_connection(tmp_path: Path) -> None:
    registry = AccountRegistry(
        tmp_path / "accounts.json",
        [account("standard-account", "1000000002", "Standard")],
    )

    registry.mark_connection_verified("standard-account", True)
    registry.set_active("standard-account")

    assert registry.connection_verified("standard-account") is False
