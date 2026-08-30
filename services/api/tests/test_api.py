from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as api_main
from app.services.accounts import AccountRegistry, BrokerAccountProfile
from app.services.market_scanner import MarketOpportunityScanner
from app.services.mt5_bridge import MT5ReadOnlyBridge
from tests.fakes import FakeMetaTrader

client = TestClient(api_main.app)


@pytest.fixture
def account_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AccountRegistry:
    terminal_path = tmp_path / "terminal64.exe"
    terminal_path.touch()
    registry = AccountRegistry(
        tmp_path / "accounts.json",
        [
            BrokerAccountProfile(
                id="standard-account",
                provider="JustMarkets",
                login="1000000002",
                server="JustMarkets-Live",
                account_type="Standard",
                terminal_path=str(terminal_path),
            ),
            BrokerAccountProfile(
                id="pro-account",
                provider="JustMarkets",
                login="1000000236",
                server="JustMarkets-Live",
                account_type="Pro",
                terminal_path=str(terminal_path),
            ),
        ],
    )
    monkeypatch.setattr(api_main, "account_registry", registry)
    fake_bridge = MT5ReadOnlyBridge(True, 1000, lambda: FakeMetaTrader())
    monkeypatch.setattr(api_main, "mt5_bridge", fake_bridge)
    monkeypatch.setattr(
        api_main,
        "market_scanner",
        MarketOpportunityScanner(fake_bridge, api_main.signal_engine),
    )
    return registry


def test_status_exposes_only_masked_active_account(
    account_registry: AccountRegistry,
) -> None:
    response = client.get("/status")

    assert response.status_code == 200
    account = response.json()["broker_account"]
    active_account = account_registry.active_account()
    assert active_account is not None
    assert account["login_masked"] == "******0002"
    assert account["login_masked"] != active_account.login
    assert account["account_type"] == "Standard"
    assert account["connection_verified"] is True
    assert response.json()["mt5"]["status"] == "connected"
    assert response.json()["mt5"]["read_only"] is True
    assert response.json()["live_trading_unlocked"] is False

    quotes = client.get("/mt5/quotes", params={"symbols": "XAUUSD"})
    assert quotes.status_code == 200
    assert quotes.json()[0]["symbol"] == "XAUUSD"

    candles = client.get("/candles/XAUUSD", params={"timeframe": "1m", "limit": 80})
    assert candles.status_code == 200
    assert candles.json()[0]["source"] == "mt5"


def test_account_switch_is_persisted_and_does_not_unlock_live_trading(
    account_registry: AccountRegistry,
) -> None:
    response = client.put("/accounts/active", json={"account_id": "pro-account"})

    assert response.status_code == 200
    assert response.json()["active_account_id"] == "pro-account"
    assert account_registry.active_account_id == "pro-account"
    status = client.get("/status").json()
    assert status["broker_account"]["login_masked"] == "******0236"
    assert status["broker_account"]["connection_verified"] is False
    assert status["mt5"]["status"] == "account_mismatch"
    assert status["live_trading_unlocked"] is False


def test_unknown_account_cannot_be_selected(account_registry: AccountRegistry) -> None:
    response = client.put("/accounts/active", json={"account_id": "missing-account"})

    assert response.status_code == 404
    assert account_registry.active_account_id == "standard-account"


def test_scan_serializes_signals_and_reasons(account_registry: AccountRegistry) -> None:
    response = client.get("/scan", params={"symbols": "XAUUSD,XAGUSD", "timeframe": "1m"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["signals"]) == 2
    assert payload["signals"][0]["reasons"]
    assert payload["news_status"]["state"] in {
        "live",
        "stale",
        "config_required",
        "error",
    }


def test_news_analysis_exposes_source_status(account_registry: AccountRegistry) -> None:
    response = client.get("/news/analysis", params={"symbols": "XAUUSD,BTCUSD"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["provider"] == "MT5 economic calendar"
    assert payload["status"]["headlines_connected"] is False
    assert isinstance(payload["events"], list)


def test_market_catalog_and_scan_use_all_tradeable_mt5_symbols(
    account_registry: AccountRegistry,
) -> None:
    catalog = client.get("/market/symbols")

    assert catalog.status_code == 200
    assert {item["symbol"] for item in catalog.json()} == {"XAUUSD", "BTCUSD"}
    assert all(item["source"] == "mt5" for item in catalog.json())

    scan_response = client.get("/market/scan", params={"timeframe": "1m", "limit": 10})
    assert scan_response.status_code == 200
    scan_payload = scan_response.json()
    assert scan_payload["available_symbols"] == 2
    assert scan_payload["scanned_symbols"] == 2
    assert scan_payload["opportunities"][0]["rank"] == 1
    assert "does not predict or guarantee profit" in scan_payload["disclaimer"]


def test_strategy_endpoint_explains_active_rules(account_registry: AccountRegistry) -> None:
    response = client.get("/strategy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Regime-Aligned Pullback"
    assert payload["version"] == "2.0"
    assert payload["adaptive_learning"] is True
    assert len(payload["components"]) == 5


def test_paper_portfolio_is_explicitly_virtual(account_registry: AccountRegistry) -> None:
    response = client.get("/paper/portfolio")

    assert response.status_code == 200
    payload = response.json()
    assert payload["engine"]["virtual_only"] is True
    assert "do not place MT5 orders" in payload["disclaimer"]
    assert payload["daily_reports"]
    assert "future_plan" in payload["learning"]
    assert "lessons" in payload["learning"]


def test_extreme_backtest_uses_verified_mt5_history(
    account_registry: AccountRegistry,
) -> None:
    response = client.get(
        "/backtests/extreme/XAUUSD",
        params={"timeframe": "1m", "limit": 200, "max_hold_bars": 15},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "mt5"
    assert payload["bars_tested"] == 200
    assert "RSI(1) extremes 10/90 over 3 bars" in payload["parameters"]
    assert isinstance(payload["trades_detail"], list)


def test_extreme_backtest_rejects_non_m1_timeframes(
    account_registry: AccountRegistry,
) -> None:
    response = client.get("/backtests/extreme/XAUUSD", params={"timeframe": "5m"})

    assert response.status_code == 422
