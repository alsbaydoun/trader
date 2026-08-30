from datetime import UTC, datetime, timedelta

from app.domain.models import Candle
from app.services.extreme_backtest import ExtremeBacktestService
from app.services.market_data import MarketDataService


def test_extreme_history_reports_indicator_outcomes() -> None:
    candles = MarketDataService().candles("XAUUSD", "1m", 240)

    result = ExtremeBacktestService().run(candles)

    assert result.source == "demo"
    assert result.bars_tested == 240
    assert result.wins + result.losses <= result.trades
    assert 0 <= result.win_rate <= 1
    assert len(result.assumptions) >= 4
    assert result.data_start < result.data_end


def test_same_candle_stop_and_target_uses_conservative_stop() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        Candle("XAUUSD", "1m", start, 100.0, 100.2, 99.8, 100.0, 100),
        Candle(
            "XAUUSD",
            "1m",
            start + timedelta(minutes=1),
            100.0,
            101.2,
            98.8,
            100.0,
            100,
        ),
    ]

    trade, exit_index = ExtremeBacktestService()._simulate_trade(
        candles,
        1,
        "buy",
        100.0,
        99.0,
        101.0,
        15,
        5,
        ["test"],
    )

    assert exit_index == 1
    assert trade.exit_reason == "stop_loss"
    assert trade.outcome == "loss"
