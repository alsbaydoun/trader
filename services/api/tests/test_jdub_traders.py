from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.models import Candle
from app.services.accounts import BrokerAccountProfile
from app.services.jdub_traders import JdubTradersService
from app.services.mt5_bridge import MT5MarketSymbol
from app.services.paper_trading import PaperTradingService


class JdubBridge:
    def __init__(self, candles: list[Candle]) -> None:
        self.candles = candles
        self.symbol = candles[0].symbol

    def scan_market_candles(
        self,
        account: BrokerAccountProfile,
        timeframe: str,
        limit: int,
        max_symbols: int,
    ) -> tuple[list[MT5MarketSymbol], dict[str, list[Candle]]]:
        del account, timeframe, limit, max_symbols
        latest = self.candles[-1].ts
        metadata = MT5MarketSymbol(
            symbol=self.symbol,
            description="Test market",
            category="Test",
            currency_base="USD",
            currency_profit="USD",
            digits=2,
            point=0.01,
            bid=self.candles[-1].close,
            ask=self.candles[-1].close + 0.01,
            spread_points=1,
            visible=True,
            trade_mode=1,
            last_tick_at=latest,
        )
        return [metadata], {self.symbol: self.candles}


def account() -> BrokerAccountProfile:
    return BrokerAccountProfile(
        id="test-account",
        provider="JustMarkets",
        login="1000000002",
        server="JustMarkets-Live",
        account_type="Standard",
    )


def make_ledger(path: Path) -> PaperTradingService:
    return PaperTradingService(
        str(path),
        enabled=True,
        starting_balance=10000,
        risk_per_trade_pct=0.05,
        max_open_positions=3,
        minimum_opportunity_score=65,
        commission_bps=1,
        slippage_bps=0,
        cycle_interval_seconds=60,
        max_position_minutes=90,
    )


def opening_range_breakout() -> list[Candle]:
    start = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
    candles = [
        Candle("TEST", "1m", start + timedelta(minutes=index), 100, 101, 99, 100.2, 1000, "mt5")
        for index in range(15)
    ]
    candles.extend(
        Candle(
            "TEST",
            "1m",
            start + timedelta(minutes=15 + index),
            100.2 + index * 0.3,
            100.8 + index * 0.3,
            100.0 + index * 0.3,
            100.5 + index * 0.3,
            1000,
            "mt5",
        )
        for index in range(5)
    )
    candles.append(
        Candle(
            "TEST",
            "1m",
            start + timedelta(minutes=20),
            102.0,
            102.6,
            101.9,
            102.4,
            1000,
            "mt5",
        )
    )
    return candles


def test_jdub_opening_range_requires_m5_confirmation_and_deduplicates_session(
    tmp_path: Path,
) -> None:
    candles = opening_range_breakout()
    service = JdubTradersService(
        make_ledger(tmp_path / "jdub.json"),
        JdubBridge(candles),
        str(tmp_path / "sessions.json"),
    )
    now = candles[-1].ts + timedelta(minutes=1)

    result = service.scan(account(), 10, now=now)
    assert result.market_scan.source == "mt5"
    assert result.market_scan.scanned_symbols == 1
    assert len(result.market_scan.opportunities) == 1
    opportunity = result.market_scan.opportunities[0]
    assert opportunity.direction.value == "buy"
    assert opportunity.signal_level == "jdub-2026-01-05-breakout"
    assert "opening range" in opportunity.reasons[0].message.lower()
    assert "5-minute" in opportunity.reasons[1].message
    assert "1-minute breakout" in opportunity.reasons[2].message

    duplicate = service.scan(account(), 10, now=now)
    assert duplicate.market_scan.opportunities == []

    reloaded = JdubTradersService(
        make_ledger(tmp_path / "jdub-reloaded.json"),
        JdubBridge(candles),
        str(tmp_path / "sessions.json"),
    )
    assert reloaded.scan(account(), 10, now=now).market_scan.opportunities == []
