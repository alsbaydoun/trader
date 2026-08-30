from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.domain.models import Candle

ExtremeDirection = Literal["buy", "sell"]
ExtremeExitReason = Literal["stop_loss", "take_profit", "time_limit", "data_end"]
ExtremeOutcome = Literal["win", "loss", "flat"]


@dataclass(frozen=True)
class ExtremeBacktestTrade:
    direction: ExtremeDirection
    signal_at: datetime
    entry_at: datetime
    exit_at: datetime
    signal_price: float
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    outcome: ExtremeOutcome
    exit_reason: ExtremeExitReason
    return_pct: float
    r_multiple: float
    score: int
    reasons: list[str]


@dataclass(frozen=True)
class ExtremeBacktestResult:
    symbol: str
    timeframe: str
    source: Literal["demo", "mt5"]
    bars_tested: int
    signals: int
    trades: int
    wins: int
    losses: int
    win_rate: float
    net_return_pct: float
    max_drawdown_pct: float
    profit_factor: float | None
    total_r: float
    average_r_multiple: float
    data_start: datetime
    data_end: datetime
    stop_atr_multiple: float
    target_r_multiple: float
    max_hold_bars: int
    parameters: list[str]
    assumptions: list[str]
    trades_detail: list[ExtremeBacktestTrade]


class ExtremeBacktestService:
    """Historical simulator for the MT5 10/90 M1 paper indicator."""

    minimum_bars = 80
    lower_extreme = 10.0
    upper_extreme = 90.0
    extreme_lookback_bars = 3
    minimum_signal_score = 4
    fast_ema_period = 5
    slow_ema_period = 20
    macd_fast_period = 5
    macd_slow_period = 6
    macd_signal_period = 3
    rsi_confirmation_period = 3
    rsi_structure_period = 7
    atr_period = 14
    stop_atr_multiple = 0.90
    target_r_multiple = 1.15
    bias_timeframe_minutes = 5

    def run(
        self,
        candles: list[Candle],
        *,
        max_hold_bars: int = 15,
        detail_limit: int = 100,
    ) -> ExtremeBacktestResult:
        ordered = sorted(candles, key=lambda candle: candle.ts)
        if len(ordered) < self.minimum_bars + 2:
            raise ValueError("Not enough M1 candles for the extreme indicator history test")
        if max_hold_bars < 1:
            raise ValueError("The maximum hold must be at least one candle")

        opens = [candle.open for candle in ordered]
        highs = [candle.high for candle in ordered]
        lows = [candle.low for candle in ordered]
        closes = [candle.close for candle in ordered]
        rsi1 = self._rsi_series(closes, 1)
        rsi3 = self._rsi_series(closes, self.rsi_confirmation_period)
        rsi7 = self._rsi_series(closes, self.rsi_structure_period)
        macd_main = [
            fast - slow
            for fast, slow in zip(
                self._ema_series(closes, self.macd_fast_period),
                self._ema_series(closes, self.macd_slow_period),
                strict=True,
            )
        ]
        macd_signal = self._ema_series(macd_main, self.macd_signal_period)
        macd_histogram = [
            main - signal for main, signal in zip(macd_main, macd_signal, strict=True)
        ]
        atr = self._atr_series(ordered, self.atr_period)
        bias = self._completed_m5_bias(ordered, closes)

        signals = 0
        trades: list[ExtremeBacktestTrade] = []
        next_available_index = self.minimum_bars
        index = self.minimum_bars
        while index < len(ordered) - 1:
            signal = self._signal_at(
                index,
                opens,
                highs,
                lows,
                closes,
                rsi1,
                rsi3,
                rsi7,
                macd_histogram,
                atr,
                bias,
            )
            if signal is None:
                index += 1
                continue
            signals += 1
            if index < next_available_index:
                index += 1
                continue

            direction, score, reasons = signal
            entry_index = index + 1
            signal_price = closes[index]
            signal_atr = atr[index]
            stop_distance = signal_atr * self.stop_atr_multiple
            target_distance = stop_distance * self.target_r_multiple
            stop_loss = (
                signal_price - stop_distance
                if direction == "buy"
                else signal_price + stop_distance
            )
            take_profit = (
                signal_price + target_distance
                if direction == "buy"
                else signal_price - target_distance
            )
            trade, exit_index = self._simulate_trade(
                ordered,
                entry_index,
                direction,
                signal_price,
                stop_loss,
                take_profit,
                max_hold_bars,
                score,
                reasons,
            )
            trades.append(trade)
            next_available_index = exit_index + 1
            index = next_available_index

        return self._result(ordered, signals, trades, max_hold_bars, detail_limit)

    def _signal_at(
        self,
        index: int,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        rsi1: list[float],
        rsi3: list[float],
        rsi7: list[float],
        macd_histogram: list[float],
        atr: list[float],
        bias: list[tuple[float, float] | None],
    ) -> tuple[ExtremeDirection, int, list[str]] | None:
        if index < 1 or atr[index] <= 0:
            return None
        lower_extreme = any(
            rsi1[index - offset] <= self.lower_extreme
            for offset in range(self.extreme_lookback_bars)
            if index - offset >= 0
        )
        upper_extreme = any(
            rsi1[index - offset] >= self.upper_extreme
            for offset in range(self.extreme_lookback_bars)
            if index - offset >= 0
        )
        bullish_rejection = (
            closes[index] > opens[index]
            and closes[index] > closes[index - 1]
            and lows[index] <= lows[index - 1]
        )
        bearish_rejection = (
            closes[index] < opens[index]
            and closes[index] < closes[index - 1]
            and highs[index] >= highs[index - 1]
        )
        bullish_rsi = rsi3[index] > rsi3[index - 1] and rsi7[index] >= rsi7[index - 1]
        bearish_rsi = rsi3[index] < rsi3[index - 1] and rsi7[index] <= rsi7[index - 1]
        bullish_macd = macd_histogram[index] > macd_histogram[index - 1]
        bearish_macd = macd_histogram[index] < macd_histogram[index - 1]
        bias_value = bias[index]
        bullish_bias = bias_value is not None and bias_value[0] >= bias_value[1]
        bearish_bias = bias_value is not None and bias_value[0] <= bias_value[1]

        buy_score = sum((lower_extreme, bullish_rejection, bullish_rsi, bullish_macd, bullish_bias))
        if (
            lower_extreme
            and bullish_rejection
            and bullish_rsi
            and bullish_macd
            and bullish_bias
            and buy_score >= self.minimum_signal_score
        ):
            return (
                "buy",
                buy_score,
                [
                    "10 extreme",
                    "bullish rejection",
                    "RSI(3) and RSI(7) rising",
                    "MACD histogram rising",
                    "completed M5 bullish bias",
                ],
            )

        sell_score = sum(
            (upper_extreme, bearish_rejection, bearish_rsi, bearish_macd, bearish_bias)
        )
        if (
            upper_extreme
            and bearish_rejection
            and bearish_rsi
            and bearish_macd
            and bearish_bias
            and sell_score >= self.minimum_signal_score
        ):
            return (
                "sell",
                sell_score,
                [
                    "90 extreme",
                    "bearish rejection",
                    "RSI(3) and RSI(7) falling",
                    "MACD histogram falling",
                    "completed M5 bearish bias",
                ],
            )
        return None

    def _simulate_trade(
        self,
        candles: list[Candle],
        entry_index: int,
        direction: ExtremeDirection,
        signal_price: float,
        stop_loss: float,
        take_profit: float,
        max_hold_bars: int,
        score: int,
        reasons: list[str],
    ) -> tuple[ExtremeBacktestTrade, int]:
        entry_candle = candles[entry_index]
        entry_price = entry_candle.open
        risk = abs(signal_price - stop_loss)
        for index in range(entry_index, len(candles)):
            candle = candles[index]
            exit_price: float | None = None
            exit_reason: ExtremeExitReason | None = None

            if direction == "buy":
                if candle.open <= stop_loss:
                    exit_price, exit_reason = candle.open, "stop_loss"
                elif candle.open >= take_profit:
                    exit_price, exit_reason = candle.open, "take_profit"
                elif candle.low <= stop_loss or candle.high >= take_profit:
                    if candle.low <= stop_loss:
                        exit_price, exit_reason = stop_loss, "stop_loss"
                    else:
                        exit_price, exit_reason = take_profit, "take_profit"
            else:
                if candle.open >= stop_loss:
                    exit_price, exit_reason = candle.open, "stop_loss"
                elif candle.open <= take_profit:
                    exit_price, exit_reason = candle.open, "take_profit"
                elif candle.high >= stop_loss or candle.low <= take_profit:
                    if candle.high >= stop_loss:
                        exit_price, exit_reason = stop_loss, "stop_loss"
                    else:
                        exit_price, exit_reason = take_profit, "take_profit"

            bars_held = index - entry_index + 1
            if exit_price is None and bars_held >= max_hold_bars:
                exit_price, exit_reason = candle.close, "time_limit"
            if exit_price is None and index == len(candles) - 1:
                exit_price, exit_reason = candle.close, "data_end"
            if exit_price is None or exit_reason is None:
                continue

            signed_move = exit_price - entry_price
            if direction == "sell":
                signed_move *= -1
            return_pct = signed_move / entry_price * 100 if entry_price else 0.0
            r_multiple = signed_move / risk if risk else 0.0
            outcome: ExtremeOutcome = (
                "win" if signed_move > 0 else "loss" if signed_move < 0 else "flat"
            )
            return (
                ExtremeBacktestTrade(
                    direction=direction,
                    signal_at=candles[entry_index - 1].ts,
                    entry_at=entry_candle.ts,
                    exit_at=candle.ts,
                    signal_price=round(signal_price, 8),
                    entry_price=round(entry_price, 8),
                    exit_price=round(exit_price, 8),
                    stop_loss=round(stop_loss, 8),
                    take_profit=round(take_profit, 8),
                    outcome=outcome,
                    exit_reason=exit_reason,
                    return_pct=round(return_pct, 4),
                    r_multiple=round(r_multiple, 4),
                    score=score,
                    reasons=reasons,
                ),
                index,
            )

        final = candles[-1]
        signed_move = final.close - entry_price
        if direction == "sell":
            signed_move *= -1
        return_pct = signed_move / entry_price * 100 if entry_price else 0.0
        r_multiple = signed_move / risk if risk else 0.0
        final_outcome: ExtremeOutcome = (
            "win" if signed_move > 0 else "loss" if signed_move < 0 else "flat"
        )
        return (
            ExtremeBacktestTrade(
                direction=direction,
                signal_at=candles[entry_index - 1].ts,
                entry_at=entry_candle.ts,
                exit_at=final.ts,
                signal_price=round(signal_price, 8),
                entry_price=round(entry_price, 8),
                exit_price=round(final.close, 8),
                stop_loss=round(stop_loss, 8),
                take_profit=round(take_profit, 8),
                outcome=final_outcome,
                exit_reason="data_end",
                return_pct=round(return_pct, 4),
                r_multiple=round(r_multiple, 4),
                score=score,
                reasons=reasons,
            ),
            len(candles) - 1,
        )

    def _result(
        self,
        candles: list[Candle],
        signals: int,
        trades: list[ExtremeBacktestTrade],
        max_hold_bars: int,
        detail_limit: int,
    ) -> ExtremeBacktestResult:
        wins = sum(trade.outcome == "win" for trade in trades)
        losses = sum(trade.outcome == "loss" for trade in trades)
        positive_r = sum(max(0.0, trade.r_multiple) for trade in trades)
        negative_r = sum(abs(min(0.0, trade.r_multiple)) for trade in trades)
        equity = 100.0
        peak = equity
        max_drawdown = 0.0
        for trade in trades:
            equity *= 1 + trade.return_pct / 100
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, (peak - equity) / peak if peak else 0.0)
        return ExtremeBacktestResult(
            symbol=candles[-1].symbol,
            timeframe=candles[-1].timeframe,
            source=candles[-1].source,
            bars_tested=len(candles),
            signals=signals,
            trades=len(trades),
            wins=wins,
            losses=losses,
            win_rate=round(wins / len(trades), 3) if trades else 0.0,
            net_return_pct=round(equity - 100.0, 3),
            max_drawdown_pct=round(max_drawdown * 100, 3),
            profit_factor=round(positive_r / negative_r, 3) if negative_r else None,
            total_r=round(sum(trade.r_multiple for trade in trades), 3),
            average_r_multiple=round(
                sum(trade.r_multiple for trade in trades) / len(trades), 3
            )
            if trades
            else 0.0,
            data_start=candles[0].ts,
            data_end=candles[-1].ts,
            stop_atr_multiple=self.stop_atr_multiple,
            target_r_multiple=self.target_r_multiple,
            max_hold_bars=max_hold_bars,
            parameters=[
                "RSI(1) extremes 10/90 over 3 bars",
                "RSI(3) and RSI(7) rejection confirmation",
                "MACD(5,6,3) histogram direction",
                "Fast/slow EMA plots with a required completed M5 EMA(20) bias",
            ],
            assumptions=[
                "Signal is evaluated on a closed M1 candle; entry is the next candle open.",
                "Stop is 0.90 ATR and target is 1.15R from the signal close.",
                "If stop and target are both touched in one candle, stop is counted first.",
                f"Open trades are closed after {max_hold_bars} M1 candles; no spread or "
                "commission data is available in candle history.",
                "Results are a historical simulation, not a prediction or profit guarantee.",
            ],
            trades_detail=list(reversed(trades[-detail_limit:])),
        )

    @staticmethod
    def _ema_series(values: list[float], period: int) -> list[float]:
        if not values:
            return []
        multiplier = 2 / (period + 1)
        result = [values[0]]
        current = values[0]
        for value in values[1:]:
            current = (value - current) * multiplier + current
            result.append(current)
        return result

    @staticmethod
    def _rsi_series(closes: list[float], period: int) -> list[float]:
        result = [50.0] * len(closes)
        if len(closes) <= period:
            return result
        gains = [max(0.0, closes[index] - closes[index - 1]) for index in range(1, period + 1)]
        losses = [max(0.0, closes[index - 1] - closes[index]) for index in range(1, period + 1)]
        average_gain = sum(gains) / period
        average_loss = sum(losses) / period
        result[period] = ExtremeBacktestService._rsi_value(average_gain, average_loss)
        for index in range(period + 1, len(closes)):
            gain = max(0.0, closes[index] - closes[index - 1])
            loss = max(0.0, closes[index - 1] - closes[index])
            average_gain = (average_gain * (period - 1) + gain) / period
            average_loss = (average_loss * (period - 1) + loss) / period
            result[index] = ExtremeBacktestService._rsi_value(average_gain, average_loss)
        return result

    @staticmethod
    def _rsi_value(average_gain: float, average_loss: float) -> float:
        if average_loss == 0:
            return 100.0 if average_gain > 0 else 50.0
        if average_gain == 0:
            return 0.0
        relative_strength = average_gain / average_loss
        return 100.0 - 100.0 / (1.0 + relative_strength)

    @staticmethod
    def _atr_series(candles: list[Candle], period: int) -> list[float]:
        result = [0.0] * len(candles)
        if len(candles) <= period:
            return result
        true_ranges: list[float] = []
        for index, candle in enumerate(candles):
            previous_close = candles[index - 1].close if index else candle.open
            true_ranges.append(
                max(
                    candle.high - candle.low,
                    abs(candle.high - previous_close),
                    abs(candle.low - previous_close),
                )
            )
        current = sum(true_ranges[:period]) / period
        result[period - 1] = current
        for index in range(period, len(candles)):
            current = (current * (period - 1) + true_ranges[index]) / period
            result[index] = current
        return result

    def _completed_m5_bias(
        self,
        candles: list[Candle],
        closes: list[float],
    ) -> list[tuple[float, float] | None]:
        groups: list[int] = []
        closes_by_group: list[float] = []
        for candle, close in zip(candles, closes, strict=True):
            group = int(candle.ts.timestamp()) // (self.bias_timeframe_minutes * 60)
            if not groups or groups[-1] != group:
                groups.append(group)
                closes_by_group.append(close)
            else:
                closes_by_group[-1] = close
        group_ema = self._ema_series(closes_by_group, self.slow_ema_period)
        group_index = {group: index for index, group in enumerate(groups)}
        bias: list[tuple[float, float] | None] = []
        for candle in candles:
            current_group = int(candle.ts.timestamp()) // (self.bias_timeframe_minutes * 60)
            completed_index = group_index.get(current_group, 0) - 1
            if completed_index < 0:
                bias.append(None)
            else:
                bias.append((closes_by_group[completed_index], group_ema[completed_index]))
        return bias
