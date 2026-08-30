from dataclasses import dataclass

from app.domain.models import Candle, Direction
from app.services.strategy import SignalEngine


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    timeframe: str
    trades: int
    win_rate: float
    net_return_pct: float
    max_drawdown_pct: float
    source: str


class BacktestService:
    max_hold_bars = 30

    def __init__(self, signal_engine: SignalEngine) -> None:
        self.signal_engine = signal_engine

    def run(self, candles: list[Candle], window: int = 80) -> BacktestResult:
        if len(candles) < window + 5:
            raise ValueError("Not enough candles for the requested backtest window")

        equity = 10000.0
        peak = equity
        wins = 0
        trades = 0
        max_drawdown = 0.0

        index = window
        while index < len(candles) - 1:
            signal = self.signal_engine.generate(candles[index - window : index])
            if signal.direction == Direction.hold:
                index += 1
                continue

            entry_candle = candles[index]
            entry_price = entry_candle.open
            if entry_price <= 0 or signal.stop_loss is None or signal.take_profit is None:
                index += 1
                continue
            exit_price, exit_index = self._simulate_trade(
                candles,
                index,
                signal.direction,
                entry_price,
                signal.stop_loss,
                signal.take_profit,
            )
            pnl = exit_price - entry_price
            if signal.direction == Direction.sell:
                pnl *= -1
            pct = pnl / entry_price
            equity *= 1 + pct
            trades += 1
            if pnl > 0:
                wins += 1
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
            index = exit_index + 1

        return BacktestResult(
            symbol=candles[-1].symbol,
            timeframe=candles[-1].timeframe,
            trades=trades,
            win_rate=round(wins / trades, 3) if trades else 0.0,
            net_return_pct=round(((equity - 10000.0) / 10000.0) * 100, 3),
            max_drawdown_pct=round(max_drawdown * 100, 3),
            source=candles[-1].source,
        )

    def _simulate_trade(
        self,
        candles: list[Candle],
        entry_index: int,
        direction: Direction,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> tuple[float, int]:
        last_index = min(len(candles) - 1, entry_index + self.max_hold_bars - 1)
        for index in range(entry_index, last_index + 1):
            candle = candles[index]
            if direction == Direction.buy:
                if candle.open <= stop_loss:
                    return candle.open, index
                if candle.open >= take_profit:
                    return candle.open, index
                if candle.low <= stop_loss:
                    return stop_loss, index
                if candle.high >= take_profit:
                    return take_profit, index
            else:
                if candle.open >= stop_loss:
                    return candle.open, index
                if candle.open <= take_profit:
                    return candle.open, index
                if candle.high >= stop_loss:
                    return stop_loss, index
                if candle.low <= take_profit:
                    return take_profit, index

            if index == last_index:
                return candle.close, index
        return candles[last_index].close, last_index
