from pathlib import Path

from app.services.accounts import BrokerAccountProfile
from app.services.extreme_scanner import ExtremeSignalScanner
from app.services.mt5_bridge import MT5ReadOnlyBridge
from tests.fakes import FakeMetaTrader


def test_attached_levels_create_one_crossing_alert_per_symbol(tmp_path: Path) -> None:
    terminal = tmp_path / "terminal64.exe"
    terminal.touch()
    account = BrokerAccountProfile(
        id="test-account",
        provider="JustMarkets",
        login="1000000002",
        server="JustMarkets-Live",
        account_type="Standard",
        terminal_path=str(terminal),
    )
    scanner = ExtremeSignalScanner(
        MT5ReadOnlyBridge(True, 1000, lambda: FakeMetaTrader()),
        cache_seconds=1,
    )

    first = scanner.scan(account, "1m", 500, 50, force=True)
    second = scanner.scan(account, "1m", 500, 50, force=True)

    assert first.source == "mt5"
    assert first.scanned_symbols == 2
    assert first.alerts
    assert all(alert.level == "upper_85" for alert in first.alerts)
    assert second.alerts == []
    assert len(second.recent_alerts) == len(first.alerts)
    assert first.readings[0].rsi1 == 100
