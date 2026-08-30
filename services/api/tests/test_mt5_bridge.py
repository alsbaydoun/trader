from pathlib import Path

from app.services.accounts import BrokerAccountProfile
from app.services.mt5_bridge import MT5ReadOnlyBridge
from tests.fakes import FakeMetaTrader


def account(terminal_path: Path, login: str = "1000000002") -> BrokerAccountProfile:
    return BrokerAccountProfile(
        id="standard-account",
        provider="JustMarkets",
        login=login,
        server="JustMarkets-Live",
        account_type="Standard",
        terminal_path=str(terminal_path),
        symbol_map={"GOLD": "XAUUSD"},
    )


def test_read_only_bridge_verifies_account_quotes_and_positions(tmp_path: Path) -> None:
    terminal_path = tmp_path / "terminal64.exe"
    terminal_path.touch()
    module = FakeMetaTrader()
    bridge = MT5ReadOnlyBridge(True, 1000, lambda: module)

    snapshot = bridge.probe(account(terminal_path))
    quotes = bridge.quotes(account(terminal_path), ["GOLD", "MISSING"])
    positions = bridge.positions(account(terminal_path))
    candles = bridge.candles(account(terminal_path), "GOLD", "1m", 80)

    assert snapshot.status == "connected"
    assert snapshot.connection_verified is True
    assert snapshot.read_only is True
    assert snapshot.balance == 1000.0
    assert len(quotes) == 1
    assert quotes[0].requested_symbol == "GOLD"
    assert quotes[0].symbol == "XAUUSD"
    assert quotes[0].bid == 2350.5
    assert len(positions) == 1
    assert positions[0].symbol == "XAUUSD"
    assert len(candles) == 80
    assert candles[0].source == "mt5"
    assert candles[0].symbol == "GOLD"


def test_account_mismatch_fails_closed_and_hides_account_data(tmp_path: Path) -> None:
    terminal_path = tmp_path / "terminal64.exe"
    terminal_path.touch()
    module = FakeMetaTrader(login="1000000236")
    bridge = MT5ReadOnlyBridge(True, 1000, lambda: module)

    snapshot = bridge.probe(account(terminal_path))

    assert snapshot.status == "account_mismatch"
    assert snapshot.connection_verified is False
    assert snapshot.selected_login_masked == "******0002"
    assert snapshot.terminal_login_masked == "******0236"
    assert bridge.quotes(account(terminal_path), ["XAUUSD"]) == []


def test_missing_package_is_reported_without_crashing(tmp_path: Path) -> None:
    terminal_path = tmp_path / "terminal64.exe"
    terminal_path.touch()

    def missing_module() -> None:
        raise ImportError

    bridge = MT5ReadOnlyBridge(True, 1000, missing_module)

    snapshot = bridge.probe(account(terminal_path))

    assert snapshot.status == "package_unavailable"
    assert snapshot.package_available is False
    assert snapshot.connection_verified is False
