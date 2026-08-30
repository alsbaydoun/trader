from datetime import UTC, datetime, timedelta

from app.domain.models import Candle, Direction
from app.services.market_data import MarketDataService
from app.services.strategy import SignalEngine


def test_signal_has_explainable_reasons() -> None:
    candles = MarketDataService().candles("XAUUSD", "1m", 120)

    signal = SignalEngine().generate(candles)

    assert signal.symbol == "XAUUSD"
    assert signal.reasons
    assert 0 <= signal.confidence <= 1


def test_flat_market_does_not_turn_one_candle_into_a_trade() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        Candle(
            "XAUUSD",
            "1m",
            start + timedelta(minutes=index),
            100.0,
            100.1,
            99.9,
            100.0,
            1000.0,
        )
        for index in range(100)
    ]

    signal = SignalEngine().generate(candles)

    assert signal.direction == Direction.hold
    assert any(reason.category == "decision" for reason in signal.reasons)
