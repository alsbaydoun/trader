from dataclasses import dataclass
from statistics import mean

from app.domain.models import Candle, Direction, Signal, SignalReason


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    version: str
    summary: str
    components: list[str]
    minimum_candles: int
    entry_threshold: float
    stop_model: str
    target_model: str
    adaptive_learning: bool
    caveat: str


class SignalEngine:
    """Selective regime-aligned pullback strategy for paper signal generation."""

    fast_period = 20
    slow_period = 50
    rsi_period = 14
    atr_period = 14
    adx_period = 14
    pullback_lookback = 4

    @staticmethod
    def definition() -> StrategyDefinition:
        return StrategyDefinition(
            name="Regime-Aligned Pullback",
            version="2.0",
            summary=(
                "A selective continuation strategy that trades a pullback only when trend, "
                "directional strength, mid-zone momentum, breakout structure, volume, and "
                "volatility conditions agree."
            ),
            components=[
                "EMA 20/50 alignment and slope",
                "ADX 14 with directional-index confirmation",
                "RSI 14 mid-zone momentum filter",
                "Pullback to EMA followed by a closed-candle break",
                "Tick-volume and ATR volatility checks",
            ],
            minimum_candles=80,
            entry_threshold=0.92,
            stop_model="1.2 ATR or 0.15% of price, whichever is wider",
            target_model="1.5:1 target distance relative to stop distance",
            adaptive_learning=True,
            caveat=(
                "This strategy intentionally produces fewer signals. It avoids fading RSI(1) "
                "extremes and blocks entries when its independent confirmations disagree. "
                "Paper learning can down-weight weak factors, but it never unlocks live trading."
            ),
        )

    def generate(self, candles: list[Candle]) -> Signal:
        if len(candles) < self.definition().minimum_candles:
            raise ValueError(
                "At least "
                f"{self.definition().minimum_candles} candles are required to generate a signal"
            )

        closes = [candle.close for candle in candles]
        current = candles[-1]
        fast_values = self._ema_series(closes, self.fast_period)
        slow_values = self._ema_series(closes, self.slow_period)
        fast = fast_values[-1]
        slow = slow_values[-1]
        atr = self._atr(candles[-(self.atr_period + 1) :])
        rsi = self._rsi(closes, self.rsi_period)
        adx, plus_di, minus_di = self._adx(candles, self.adx_period)
        volatility_pct = atr / current.close if current.close else 1.0
        average_volume = mean(candle.volume for candle in candles[-21:-1])
        volume_ratio = current.volume / average_volume if average_volume > 0 else 1.0
        fast_slope = fast - fast_values[-4]
        slow_slope = slow - slow_values[-4]
        pullback_candles = candles[-(self.pullback_lookback + 1) : -1]

        trend_up = (
            fast > slow and fast_slope > atr * 0.05 and slow_slope >= 0 and plus_di > minus_di
        )
        trend_down = (
            fast < slow and fast_slope < -atr * 0.05 and slow_slope <= 0 and minus_di > plus_di
        )
        pullback_up = any(
            candle.low <= fast + atr * 0.75 and candle.close >= fast
            for candle in pullback_candles
        )
        pullback_down = any(
            candle.high >= fast - atr * 0.75 and candle.close <= fast
            for candle in pullback_candles
        )
        recent_high = max(candle.high for candle in candles[-3:-1])
        recent_low = min(candle.low for candle in candles[-3:-1])
        breakout_up = (
            current.close > recent_high
            and current.close > current.open
            and current.close > fast
        )
        breakout_down = (
            current.close < recent_low
            and current.close < current.open
            and current.close < fast
        )
        momentum_up = 52.0 <= rsi <= 68.0
        momentum_down = 32.0 <= rsi <= 48.0
        strength_ok = adx >= 20.0
        volatility_ok = 0 < volatility_pct <= 0.015
        volume_ok = volume_ratio >= 0.70

        long_score = self._score(
            trend_up,
            pullback_up,
            breakout_up,
            momentum_up,
            strength_ok and plus_di > minus_di,
            volume_ok,
            volatility_ok,
        )
        short_score = self._score(
            trend_down,
            pullback_down,
            breakout_down,
            momentum_down,
            strength_ok and minus_di > plus_di,
            volume_ok,
            volatility_ok,
        )
        long_setup = (
            trend_up
            and pullback_up
            and breakout_up
            and momentum_up
            and strength_ok
            and plus_di > minus_di
            and volume_ok
            and volatility_ok
        )
        short_setup = (
            trend_down
            and pullback_down
            and breakout_down
            and momentum_down
            and strength_ok
            and minus_di > plus_di
            and volume_ok
            and volatility_ok
        )

        reasons: list[SignalReason] = [
            self._direction_reason(
                "trend",
                trend_up,
                trend_down,
                "EMA 20/50 and slope favor "
                f"{'buyers' if trend_up else 'sellers' if trend_down else 'neither'}.",
                0.28,
            ),
            SignalReason(
                "pullback",
                (
                    f"The prior {self.pullback_lookback} candles "
                    f"{'touched' if pullback_up or pullback_down else 'did not touch'} "
                    "the fast EMA before the current trigger."
                ),
                "bullish" if pullback_up else "bearish" if pullback_down else "neutral",
                0.18,
            ),
            SignalReason(
                "breakout",
                "The latest candle broke the previous high."
                if breakout_up
                else "The latest candle broke the previous low."
                if breakout_down
                else "The latest candle has no confirmed directional break.",
                "bullish" if breakout_up else "bearish" if breakout_down else "neutral",
                0.22,
            ),
            SignalReason(
                "momentum",
                f"RSI(14) is {rsi:.1f}; the strategy accepts the mid-zone "
                "instead of chasing an extreme.",
                "bullish" if momentum_up else "bearish" if momentum_down else "neutral",
                0.12,
            ),
            SignalReason(
                "strength",
                f"ADX(14) is {adx:.1f}; +DI is {plus_di:.1f} and -DI is {minus_di:.1f}.",
                "bullish" if plus_di > minus_di else "bearish" if minus_di > plus_di else "neutral",
                0.12,
            ),
            SignalReason(
                "volume",
                f"Current tick volume is {volume_ratio:.2f}x the prior 20-candle average.",
                "neutral" if volume_ok else "risk",
                0.05,
            ),
            SignalReason(
                "risk",
                f"ATR is {volatility_pct * 100:.3f}% of price; volatility is "
                f"{'inside' if volatility_ok else 'outside'} the allowed range.",
                "neutral" if volatility_ok else "risk",
                0.03,
            ),
        ]

        direction = Direction.hold
        score = 0.0
        if (
            long_setup
            and long_score >= self.definition().entry_threshold
            and long_score > short_score
        ):
            direction = Direction.buy
            score = long_score
        elif (
            short_setup
            and short_score >= self.definition().entry_threshold
            and short_score > long_score
        ):
            direction = Direction.sell
            score = short_score

        if direction == Direction.hold:
            reasons.append(
                SignalReason(
                    "decision",
                    "WAIT: the full regime, pullback, trigger, momentum, strength, "
                    "volume, and volatility stack is not aligned.",
                    "neutral",
                    0.10,
                )
            )

        stop_distance = max(atr * 1.2, current.close * 0.0015)
        target_distance = stop_distance * 1.5
        stop_loss = None
        take_profit = None
        if direction == Direction.buy:
            stop_loss = current.close - stop_distance
            take_profit = current.close + target_distance
        elif direction == Direction.sell:
            stop_loss = current.close + stop_distance
            take_profit = current.close - target_distance

        confidence = min(0.90, max(0.05, 0.35 + score * 0.55))
        return Signal(
            symbol=current.symbol,
            timeframe=current.timeframe,
            direction=direction,
            confidence=round(confidence, 3),
            entry=round(current.close, 5),
            stop_loss=round(stop_loss, 5) if stop_loss else None,
            take_profit=round(take_profit, 5) if take_profit else None,
            reasons=reasons,
            source=current.source,
        )

    @staticmethod
    def _score(*conditions: bool) -> float:
        weights = (0.28, 0.18, 0.22, 0.12, 0.12, 0.05, 0.03)
        return round(
            sum(
                weight
                for condition, weight in zip(conditions, weights, strict=True)
                if condition
            ),
            3,
        )

    @staticmethod
    def _direction_reason(
        category: str,
        bullish: bool,
        bearish: bool,
        message: str,
        weight: float,
    ) -> SignalReason:
        return SignalReason(
            category,
            message,
            "bullish" if bullish else "bearish" if bearish else "neutral",
            weight,
        )

    @staticmethod
    def _ema_series(values: list[float], period: int) -> list[float]:
        if not values:
            return []
        seed = mean(values[: min(period, len(values))])
        result = [seed]
        multiplier = 2 / (period + 1)
        for value in values[1:]:
            seed = (value - seed) * multiplier + seed
            result.append(seed)
        return result

    @classmethod
    def _rsi(cls, values: list[float], period: int) -> float:
        if len(values) <= period:
            return 50.0
        gains = 0.0
        losses = 0.0
        for index in range(-period, 0):
            change = values[index] - values[index - 1]
            gains += max(change, 0.0)
            losses += max(-change, 0.0)
        if losses == 0:
            return 100.0 if gains else 50.0
        return 100.0 - (100.0 / (1.0 + gains / losses))

    @staticmethod
    def _atr(candles: list[Candle]) -> float:
        if len(candles) < 2:
            return 0.0
        ranges: list[float] = []
        previous_close = candles[0].close
        for candle in candles[1:]:
            ranges.append(
                max(
                    candle.high - candle.low,
                    abs(candle.high - previous_close),
                    abs(candle.low - previous_close),
                )
            )
            previous_close = candle.close
        return mean(ranges) if ranges else 0.0

    @classmethod
    def _adx(cls, candles: list[Candle], period: int) -> tuple[float, float, float]:
        if len(candles) <= period * 2:
            return 0.0, 0.0, 0.0
        true_ranges: list[float] = []
        plus_moves: list[float] = []
        minus_moves: list[float] = []
        for current, previous in zip(candles[1:], candles[:-1], strict=True):
            true_ranges.append(
                max(
                    current.high - current.low,
                    abs(current.high - previous.close),
                    abs(current.low - previous.close),
                )
            )
            up_move = current.high - previous.high
            down_move = previous.low - current.low
            plus_moves.append(up_move if up_move > down_move and up_move > 0 else 0.0)
            minus_moves.append(down_move if down_move > up_move and down_move > 0 else 0.0)

        true_range = sum(true_ranges[:period])
        plus_move = sum(plus_moves[:period])
        minus_move = sum(minus_moves[:period])
        dx_values: list[float] = []
        plus_di = minus_di = 0.0
        for index in range(period - 1, len(true_ranges)):
            if index >= period:
                true_range = true_range - true_range / period + true_ranges[index]
                plus_move = plus_move - plus_move / period + plus_moves[index]
                minus_move = minus_move - minus_move / period + minus_moves[index]
            if true_range <= 0:
                continue
            plus_di = plus_move / true_range * 100
            minus_di = minus_move / true_range * 100
            denominator = plus_di + minus_di
            if denominator > 0:
                dx_values.append(abs(plus_di - minus_di) / denominator * 100)
        if not dx_values:
            return 0.0, plus_di, minus_di
        adx = mean(dx_values[-period:])
        return adx, plus_di, minus_di
