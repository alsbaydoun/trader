from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import tanh
from threading import RLock
from uuid import uuid4

from app.domain.models import Candle
from app.services.accounts import BrokerAccountProfile
from app.services.mt5_bridge import MT5ReadOnlyBridge


@dataclass(frozen=True)
class ExtremeReading:
    symbol: str
    price: float
    score: float
    level: str
    rsi1: float
    macd: float
    macd_signal: float
    macd_histogram: float
    ema_fast: float
    ema_slow: float
    recommendation: str
    reasons: list[str]
    source: str
    detected_at: datetime
    rsi3: float = 50.0
    rsi7: float = 50.0
    momentum_pct: float = 0.0
    candle_direction: str = "neutral"
    atr_pct: float = 0.0
    reversal_confirmed: bool = False


@dataclass(frozen=True)
class ExtremeAlert:
    id: str
    symbol: str
    level: str
    score: float
    rsi1: float
    macd: float
    macd_signal: float
    ema_fast: float
    ema_slow: float
    recommendation: str
    reasons: list[str]
    triggered_at: datetime
    source: str
    rsi3: float = 50.0
    rsi7: float = 50.0
    momentum_pct: float = 0.0
    candle_direction: str = "neutral"
    atr_pct: float = 0.0
    reversal_confirmed: bool = False


@dataclass(frozen=True)
class ExtremeScanResult:
    source: str
    timeframe: str
    available_symbols: int
    scanned_symbols: int
    generated_at: datetime
    upper_level: float
    lower_level: float
    readings: list[ExtremeReading]
    alerts: list[ExtremeAlert]
    recent_alerts: list[ExtremeAlert]
    disclaimer: str


class ExtremeSignalScanner:
    """Whole-catalog RSI/MACD/MA monitor with threshold-crossing alerts."""

    upper_level = 85.0
    lower_level = 15.0

    def __init__(
        self,
        bridge: MT5ReadOnlyBridge,
        cache_seconds: int = 10,
        alert_cooldown_seconds: int = 300,
    ) -> None:
        self.bridge = bridge
        self.cache_for = timedelta(seconds=cache_seconds)
        self.alert_cooldown = timedelta(seconds=alert_cooldown_seconds)
        self._states: dict[str, tuple[str, datetime]] = {}
        self._recent_alerts: list[ExtremeAlert] = []
        self._cache_key = ""
        self._cached_at: datetime | None = None
        self._cached: ExtremeScanResult | None = None
        self._lock = RLock()

    def scan(
        self,
        account: BrokerAccountProfile | None,
        timeframe: str,
        max_symbols: int,
        result_limit: int,
        force: bool = False,
    ) -> ExtremeScanResult:
        with self._lock:
            now = datetime.now(UTC)
            key = f"{account.id if account else 'none'}:{timeframe}:{max_symbols}"
            if (
                not force
                and self._cached is not None
                and self._cache_key == key
                and self._cached_at is not None
                and now - self._cached_at < self.cache_for
            ):
                return self._limited(self._cached, result_limit)

            symbols, candles_by_symbol = self.bridge.scan_market_candles(
                account,
                timeframe,
                60,
                max_symbols,
            )
            readings: list[ExtremeReading] = []
            alerts: list[ExtremeAlert] = []
            for symbol, candles in candles_by_symbol.items():
                reading = self._reading(symbol, candles)
                readings.append(reading)
                alert = self._threshold_alert(reading)
                if alert is not None:
                    alerts.append(alert)
                    self._recent_alerts.insert(0, alert)
            self._recent_alerts = self._recent_alerts[:200]
            readings.sort(key=lambda item: abs(item.score - 50), reverse=True)
            result = ExtremeScanResult(
                source="mt5" if symbols else "unavailable",
                timeframe=timeframe,
                available_symbols=len(symbols),
                scanned_symbols=len(candles_by_symbol),
                generated_at=now,
                upper_level=self.upper_level,
                lower_level=self.lower_level,
                readings=readings,
                alerts=alerts,
                recent_alerts=list(self._recent_alerts),
                disclaimer=(
                    "RSI(1) is intentionally highly reactive and can remain extreme. MACD and "
                    "moving average values are confirmation context, not a guaranteed reversal "
                    "signal. Alerts are decision support and never place orders."
                ),
            )
            self._cache_key = key
            self._cached_at = now
            self._cached = result
            return self._limited(result, result_limit)

    def _reading(self, symbol: str, candles: list[Candle]) -> ExtremeReading:
        closes = [candle.close for candle in candles]
        ema_fast = self._ema(closes, 5)
        ema_slow = self._ema(closes, 6)
        macd_values = self._macd_values(closes, 5, 6)
        macd = macd_values[-1]
        macd_signal = self._ema(macd_values, 3)
        macd_histogram = macd - macd_signal
        atr = self._atr(candles[-15:])
        macd_bias = 50.0 + 50.0 * tanh((macd / atr) * 3.0) if atr else 50.0
        rsi1 = self._rsi_one(closes)
        # Keep RSI(1) dominant while scoring MACD/MA context for a reversal, so the
        # strict 85/15 paper filter is attainable instead of self-contradictory.
        if rsi1 >= 50:
            reversal_macd_bias = 100.0 - macd_bias
            reversal_trend_bias = 100.0 if ema_fast < ema_slow else 0.0
        else:
            reversal_macd_bias = macd_bias
            reversal_trend_bias = 100.0 if ema_fast > ema_slow else 0.0
        score = max(
            0.0,
            min(100.0, rsi1 * 0.9 + reversal_macd_bias * 0.05 + reversal_trend_bias * 0.05),
        )
        level = self._level(score)
        rsi3 = self._rsi(closes, 3)
        rsi7 = self._rsi(closes, 7)
        momentum_pct = self._momentum_pct(closes, 4)
        candle_direction = self._candle_direction(candles[-1])
        reversal_confirmed = (
            level == "upper_85"
            and candle_direction == "bearish"
            and rsi3 < 70
            and rsi7 < 60
            and momentum_pct < 0
            and macd_histogram < 0
            and ema_fast < ema_slow
        ) or (
            level == "lower_15"
            and candle_direction == "bullish"
            and rsi3 > 30
            and rsi7 > 40
            and momentum_pct > 0
            and macd_histogram > 0
            and ema_fast > ema_slow
        )
        recommendation, reasons = self._recommendation(
            level,
            rsi1,
            rsi3,
            rsi7,
            momentum_pct,
            macd,
            macd_signal,
            macd_histogram,
            ema_fast,
            ema_slow,
            atr,
            candle_direction,
            reversal_confirmed,
        )
        return ExtremeReading(
            symbol=symbol,
            price=closes[-1],
            score=round(score, 2),
            level=level,
            rsi1=round(rsi1, 2),
            macd=round(macd, 8),
            macd_signal=round(macd_signal, 8),
            macd_histogram=round(macd_histogram, 8),
            ema_fast=round(ema_fast, 8),
            ema_slow=round(ema_slow, 8),
            recommendation=recommendation,
            reasons=reasons,
            source=candles[-1].source,
            detected_at=candles[-1].ts,
            rsi3=round(rsi3, 2),
            rsi7=round(rsi7, 2),
            momentum_pct=round(momentum_pct, 4),
            candle_direction=candle_direction,
            atr_pct=round(atr / closes[-1] * 100, 4) if closes[-1] else 0.0,
            reversal_confirmed=reversal_confirmed,
        )

    def _threshold_alert(self, reading: ExtremeReading) -> ExtremeAlert | None:
        if reading.level == "neutral":
            self._states[reading.symbol] = ("neutral", datetime.now(UTC))
            return None
        now = datetime.now(UTC)
        previous_level, previous_alert_at = self._states.get(reading.symbol, ("neutral", now))
        self._states[reading.symbol] = (reading.level, now)
        entered_level = previous_level != reading.level
        cooldown_elapsed = now - previous_alert_at >= self.alert_cooldown
        if not entered_level and not cooldown_elapsed:
            return None
        return ExtremeAlert(
            id=f"extreme-{uuid4().hex[:12]}",
            symbol=reading.symbol,
            level=reading.level,
            score=reading.score,
            rsi1=reading.rsi1,
            macd=reading.macd,
            macd_signal=reading.macd_signal,
            ema_fast=reading.ema_fast,
            ema_slow=reading.ema_slow,
            recommendation=reading.recommendation,
            reasons=reading.reasons,
            triggered_at=now,
            source=reading.source,
            rsi3=reading.rsi3,
            rsi7=reading.rsi7,
            momentum_pct=reading.momentum_pct,
            candle_direction=reading.candle_direction,
            atr_pct=reading.atr_pct,
            reversal_confirmed=reading.reversal_confirmed,
        )

    def _recommendation(
        self,
        level: str,
        rsi1: float,
        rsi3: float,
        rsi7: float,
        momentum_pct: float,
        macd: float,
        macd_signal: float,
        macd_histogram: float,
        ema_fast: float,
        ema_slow: float,
        atr: float,
        candle_direction: str,
        reversal_confirmed: bool,
    ) -> tuple[str, list[str]]:
        if level == "upper_85":
            confirmed = reversal_confirmed
            recommendation = (
                "Scalp sell candidate: 85/15 extreme plus a bearish rejection and "
                "falling MACD histogram."
                if confirmed
                else "Overbought setup: wait for a bearish rejection and falling "
                "MACD histogram before selling."
            )
        elif level == "lower_15":
            confirmed = reversal_confirmed
            recommendation = (
                "Scalp buy candidate: 85/15 extreme plus a bullish rejection and "
                "rising MACD histogram."
                if confirmed
                else "Oversold setup: wait for a bullish rejection and rising "
                "MACD histogram before buying."
            )
        else:
            recommendation = "No extreme-level action."
        macd_state = "above" if macd >= 0 else "below"
        ma_state = "above" if ema_fast >= ema_slow else "below"
        reasons = [
            (
                f"RSI(1) is {rsi1:.2f}, with alert levels at {self.upper_level:.2f} "
                f"and {self.lower_level:.2f}."
            ),
            (
                f"MACD(5,6,3) is {macd_state} zero at {macd:.8g}; signal is "
                f"{macd_signal:.8g} and histogram is {macd_histogram:.8g}."
            ),
            (
                f"RSI(3) is {rsi3:.2f} and RSI(7) is {rsi7:.2f}; the latest candle is "
                f"{candle_direction}."
            ),
            f"Four-candle momentum is {momentum_pct:+.4f}%; reversal stack is "
            f"{'confirmed' if reversal_confirmed else 'not confirmed'}.",
            (
                f"Fast moving average is {ma_state} the slow moving average; ATR context is "
                f"{atr:.8g}. Reversal trigger: {'confirmed' if reversal_confirmed else 'waiting'}."
            ),
        ]
        return recommendation, reasons

    def _level(self, score: float) -> str:
        if score >= self.upper_level:
            return "upper_85"
        if score <= self.lower_level:
            return "lower_15"
        return "neutral"

    @staticmethod
    def _rsi_one(closes: list[float]) -> float:
        if len(closes) < 2:
            return 50.0
        change = closes[-1] - closes[-2]
        if change > 0:
            return 100.0
        if change < 0:
            return 0.0
        return 50.0

    @staticmethod
    def _rsi(closes: list[float], period: int) -> float:
        if len(closes) < period + 1:
            return 50.0
        changes = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
        window = changes[-period:]
        gains = sum(change for change in window if change > 0) / period
        losses = sum(-change for change in window if change < 0) / period
        if losses == 0:
            return 100.0 if gains > 0 else 50.0
        if gains == 0:
            return 0.0
        relative_strength = gains / losses
        return 100.0 - (100.0 / (1.0 + relative_strength))

    @staticmethod
    def _momentum_pct(closes: list[float], lookback: int) -> float:
        if len(closes) <= lookback or closes[-lookback - 1] == 0:
            return 0.0
        return (closes[-1] - closes[-lookback - 1]) / closes[-lookback - 1] * 100

    @staticmethod
    def _candle_direction(candle: Candle) -> str:
        if candle.close > candle.open:
            return "bullish"
        if candle.close < candle.open:
            return "bearish"
        return "neutral"

    @staticmethod
    def _macd_values(closes: list[float], fast_period: int, slow_period: int) -> list[float]:
        if not closes:
            return [0.0]
        fast_multiplier = 2 / (fast_period + 1)
        slow_multiplier = 2 / (slow_period + 1)
        fast = slow = closes[0]
        values = [0.0]
        for close in closes[1:]:
            fast = (close - fast) * fast_multiplier + fast
            slow = (close - slow) * slow_multiplier + slow
            values.append(fast - slow)
        return values

    @staticmethod
    def _ema(values: list[float], period: int) -> float:
        multiplier = 2 / (period + 1)
        value = values[0]
        for item in values[1:]:
            value = (item - value) * multiplier + value
        return value

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
        return sum(ranges) / len(ranges) if ranges else 0.0

    @staticmethod
    def _limited(result: ExtremeScanResult, limit: int) -> ExtremeScanResult:
        return ExtremeScanResult(
            source=result.source,
            timeframe=result.timeframe,
            available_symbols=result.available_symbols,
            scanned_symbols=result.scanned_symbols,
            generated_at=result.generated_at,
            upper_level=result.upper_level,
            lower_level=result.lower_level,
            readings=result.readings[:limit],
            alerts=result.alerts,
            recent_alerts=result.recent_alerts,
            disclaimer=result.disclaimer,
        )
