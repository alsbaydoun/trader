from datetime import UTC, datetime, timedelta
from math import sin
from random import Random

from app.domain.models import Candle


class MarketDataService:
    """Deterministic demo market data until a paid feed is configured."""

    def candles(self, symbol: str, timeframe: str = "1m", limit: int = 240) -> list[Candle]:
        rng = Random(f"{symbol}:{timeframe}:{limit}")
        base = self._base_price(symbol)
        step = self._timeframe_minutes(timeframe)
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        candles: list[Candle] = []
        last_close = base

        for index in range(limit):
            ts = now - timedelta(minutes=step * (limit - index))
            wave = sin(index / 9.0) * base * 0.0018
            drift = (index - limit / 2) * base * 0.000004
            noise = (rng.random() - 0.5) * base * 0.0012
            close = max(0.01, base + wave + drift + noise)
            open_price = last_close
            high = max(open_price, close) + rng.random() * base * 0.0008
            low = min(open_price, close) - rng.random() * base * 0.0008
            volume = 500 + rng.random() * 2500
            candles.append(Candle(symbol, timeframe, ts, open_price, high, low, close, volume))
            last_close = close

        return candles

    @staticmethod
    def _base_price(symbol: str) -> float:
        return {
            "XAUUSD": 2345.0,
            "XAGUSD": 31.2,
            "BTCUSD": 64000.0,
            "US100.std": 19800.0,
            "US30.std": 40100.0,
            "WTI.m": 78.5,
            "BRENT.m": 82.4,
        }.get(symbol, 100.0)

    @staticmethod
    def _timeframe_minutes(timeframe: str) -> int:
        if timeframe.endswith("m"):
            return max(1, int(timeframe[:-1]))
        if timeframe.endswith("h"):
            return max(1, int(timeframe[:-1])) * 60
        if timeframe.endswith("d"):
            return max(1, int(timeframe[:-1])) * 1440
        return 1
