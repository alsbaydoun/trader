from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.models import Candle
from app.services.accounts import BrokerAccountProfile
from app.services.extreme_paper_trading import ExtremePaperTradingService
from app.services.extreme_scanner import ExtremeAlert, ExtremeReading, ExtremeScanResult
from app.services.paper_trading import PaperTradingService


class CandleBridge:
    def __init__(self) -> None:
        self.close = 100.0

    def candles(
        self,
        account: BrokerAccountProfile | None,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[Candle]:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        return [
            Candle(
                symbol,
                timeframe,
                now + timedelta(minutes=index),
                self.close,
                self.close + 0.2,
                self.close - 0.2,
                self.close,
                1000,
                "mt5",
            )
            for index in range(limit)
        ]


def make_service(path: Path, bridge: CandleBridge) -> ExtremePaperTradingService:
    ledger = PaperTradingService(
        str(path),
        enabled=True,
        starting_balance=10000,
        risk_per_trade_pct=0.1,
        max_open_positions=10,
        minimum_opportunity_score=70,
        commission_bps=0,
        slippage_bps=0,
        cycle_interval_seconds=15,
        max_position_minutes=240,
        trade_source="extreme-scanner-virtual",
    )
    return ExtremePaperTradingService(ledger, bridge, confirmed_only=True)


def account() -> BrokerAccountProfile:
    return BrokerAccountProfile(
        id="test-account",
        provider="JustMarkets",
        login="1000000002",
        server="JustMarkets-Live",
        account_type="Standard",
    )


def scan(*, now: datetime, alerts: list[ExtremeAlert]) -> ExtremeScanResult:
    reading = ExtremeReading(
        symbol="XAUUSD",
        price=100,
        score=90,
        level="upper_85",
        rsi1=100,
        macd=-0.2,
        macd_signal=-0.1,
        macd_histogram=0,
        ema_fast=99,
        ema_slow=100,
        recommendation="Reversal sell watch: MACD and MA confirm weakness.",
        reasons=["RSI(1) reached the upper extreme."],
        source="mt5",
        detected_at=now,
    )
    return ExtremeScanResult(
        source="mt5",
        timeframe="1m",
        available_symbols=1,
        scanned_symbols=1,
        generated_at=now,
        upper_level=85,
        lower_level=15,
        readings=[reading],
        alerts=alerts,
        recent_alerts=alerts,
        disclaimer="test",
    )


def alert(triggered_at: datetime) -> ExtremeAlert:
    return ExtremeAlert(
        id="extreme-test-alert",
        symbol="XAUUSD",
        level="upper_85",
        score=90,
        rsi1=100,
        macd=-0.2,
        macd_signal=-0.1,
        ema_fast=99,
        ema_slow=100,
        recommendation="Reversal sell watch: MACD and MA confirm weakness.",
        reasons=["RSI(1) reached the upper extreme."],
        triggered_at=triggered_at,
        source="mt5",
        rsi3=60,
        rsi7=50,
        momentum_pct=-0.1,
        candle_direction="bearish",
        reversal_confirmed=True,
    )


def test_confirmed_extreme_trade_records_signal_to_exit_result(tmp_path: Path) -> None:
    bridge = CandleBridge()
    service = make_service(tmp_path / "extreme.json", bridge)
    started = datetime(2026, 1, 1, tzinfo=UTC)

    opened = service.process_scan(scan(now=started, alerts=[alert(started)]), account())

    assert opened.metrics.open_positions == 1
    trade = opened.open_positions[0]
    assert trade.source == "extreme-scanner-virtual"
    assert trade.signal_at == started
    assert trade.signal_price == 100
    assert trade.signal_level == "upper_85"
    assert trade.direction.value == "sell"

    bridge.close = 96
    finished = service.process_scan(
        scan(now=started + timedelta(minutes=1), alerts=[]),
        account(),
    )

    assert finished.metrics.open_positions == 0
    assert finished.metrics.closed_trades == 1
    assert finished.metrics.winning_trades == 1
    assert finished.closed_trades[0].exit_reason == "take_profit"
    assert finished.closed_trades[0].net_pnl > 0
    assert finished.closed_trades[0].signal_at == started
    assert make_service(tmp_path / "extreme.json", bridge).snapshot().metrics.closed_trades == 1


def test_unconfirmed_extreme_alert_is_not_entered(tmp_path: Path) -> None:
    bridge = CandleBridge()
    service = make_service(tmp_path / "extreme.json", bridge)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    unconfirmed = ExtremeAlert(
        **{**alert(started).__dict__, "macd": 0.2, "ema_fast": 101, "ema_slow": 100}
    )

    result = service.process_scan(scan(now=started, alerts=[unconfirmed]), account())

    assert result.metrics.open_positions == 0
    assert result.metrics.closed_trades == 0
    assert result.engine.eligible_candidates == 0
