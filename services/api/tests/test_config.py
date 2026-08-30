from app.core.config import Settings


def test_mt5_profile_masks_login_and_stays_locked_without_password() -> None:
    settings = Settings(
        mt5_login="1000000236",
        mt5_server="JustMarkets-Live",
        mt5_account_type="Pro",
        broker_adapter="mt5",
        trading_mode="live",
        live_trading_enabled=True,
        live_trading_acknowledgement="I understand live trading can lose money",
        mt5_read_only_enabled=False,
    )

    assert settings.mt5_login_masked == "******0236"
    assert settings.mt5_profile_configured is True
    assert settings.mt5_credentials_configured is False
    assert settings.live_trading_unlocked is False


def test_mt5_live_unlock_requires_complete_connection_configuration() -> None:
    settings = Settings(
        mt5_login="1000000236",
        mt5_password="not-a-real-password",
        mt5_server="JustMarkets-Live",
        mt5_terminal_path=r"C:\\Program Files\\MetaTrader 5\\terminal64.exe",
        broker_adapter="mt5",
        trading_mode="live",
        live_trading_enabled=True,
        live_trading_acknowledgement="I understand live trading can lose money",
        mt5_read_only_enabled=False,
    )

    assert settings.mt5_connection_configured is True
    assert settings.live_trading_unlocked is True


def test_mt5_read_only_mode_blocks_live_unlock() -> None:
    settings = Settings(
        mt5_login="1000000236",
        mt5_password="not-a-real-password",
        mt5_server="JustMarkets-Live",
        mt5_terminal_path=r"C:\\Program Files\\MetaTrader 5\\terminal64.exe",
        broker_adapter="mt5",
        trading_mode="live",
        live_trading_enabled=True,
        live_trading_acknowledgement="I understand live trading can lose money",
        mt5_read_only_enabled=True,
    )

    assert settings.mt5_connection_configured is True
    assert settings.live_trading_unlocked is False
