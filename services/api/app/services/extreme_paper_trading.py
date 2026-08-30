from collections.abc import Iterable
from math import isfinite
from typing import Literal

from app.domain.models import Candle, Direction, Position, SignalReason
from app.services.accounts import BrokerAccountProfile
from app.services.extreme_scanner import ExtremeAlert, ExtremeReading, ExtremeScanResult
from app.services.market_scanner import MarketOpportunity, MarketScanResult
from app.services.mt5_bridge import MT5ReadOnlyBridge
from app.services.paper_trading import PaperPortfolio, PaperTradingService


class ExtremePaperTradingService:
    """Feeds confirmed 85/15 scanner entries into a separate paper-only ledger."""

    def __init__(
        self,
        ledger: PaperTradingService,
        bridge: MT5ReadOnlyBridge,
        *,
        confirmed_only: bool = True,
    ) -> None:
        self.ledger = ledger
        self.bridge = bridge
        self.confirmed_only = confirmed_only

    @property
    def enabled(self) -> bool:
        return self.ledger.enabled

    @property
    def timeframe(self) -> str:
        return self.ledger.timeframe

    def snapshot(self) -> PaperPortfolio:
        return self.ledger.snapshot()

    def positions(self) -> list[Position]:
        return self.ledger.positions()

    def update_control(
        self,
        *,
        enabled: bool | None = None,
        timeframe: str | None = None,
        minimum_opportunity_score: float | None = None,
        max_open_positions: int | None = None,
    ) -> PaperPortfolio:
        return self.ledger.update_control(
            enabled=enabled,
            timeframe=timeframe,
            minimum_opportunity_score=minimum_opportunity_score,
            max_open_positions=max_open_positions,
        )

    def close_trade(self, trade_id: str, price: float) -> PaperPortfolio:
        return self.ledger.close_trade(trade_id, price)

    def reset(self) -> PaperPortfolio:
        return self.ledger.reset()

    def process_scan(
        self,
        scan: ExtremeScanResult,
        account: BrokerAccountProfile | None,
    ) -> PaperPortfolio:
        if scan.source != "mt5" or account is None:
            self.ledger.record_error(
                "The extreme virtual cycle was skipped because verified MT5 market data is "
                "unavailable."
            )
            return self.ledger.snapshot()

        readings = {reading.symbol: reading for reading in scan.readings}
        alerts = [
            alert for alert in scan.alerts if not self.confirmed_only or self._is_confirmed(alert)
        ]
        alerts.sort(key=lambda alert: abs(alert.score - 50), reverse=True)
        symbols = {position.symbol for position in self.ledger.positions()}
        symbols.update(alert.symbol for alert in alerts)

        candles_by_symbol: dict[str, list[Candle]] = {}
        prices: dict[str, Candle] = {}
        for symbol in symbols:
            current_candles = self.bridge.candles(account, symbol, scan.timeframe, 80)
            if not current_candles:
                continue
            candles_by_symbol[symbol] = current_candles
            prices[symbol] = current_candles[-1]

        opportunities: list[MarketOpportunity] = []
        for rank, alert in enumerate(alerts, start=1):
            reading = readings.get(alert.symbol)
            signal_candles = candles_by_symbol.get(alert.symbol)
            if reading is None or not signal_candles:
                continue
            opportunity = self._to_opportunity(rank, alert, reading.price, signal_candles)
            if opportunity is not None:
                opportunities.append(opportunity)

        market_scan = MarketScanResult(
            source=scan.source,
            timeframe=scan.timeframe,
            available_symbols=scan.available_symbols,
            scanned_symbols=scan.scanned_symbols,
            generated_at=scan.generated_at,
            disclaimer=(
                "Extreme scanner virtual results use only confirmed 85/15 entries, observed MT5 "
                "prices, configured costs, and the same stop, target, time-limit, and risk rules "
                "as the paper engine. They do not predict or guarantee profit."
            ),
            opportunities=opportunities,
        )
        return self.ledger.process_cycle(
            market_scan,
            prices,
            account.id,
            now=scan.generated_at,
        )

    def process_readings(
        self,
        scan: ExtremeScanResult,
        account: BrokerAccountProfile | None,
        readings: Iterable[ExtremeReading],
        *,
        strategy_label: str,
        stop_atr: float = 1.25,
        target_r: float = 1.5,
    ) -> PaperPortfolio:
        """Run a paper ledger from strategy-filtered readings without broker orders."""
        if scan.source != "mt5" or account is None:
            self.ledger.record_error(
                f"The {strategy_label} virtual cycle was skipped because verified MT5 market "
                "data is unavailable."
            )
            return self.ledger.snapshot()

        candidates = sorted(
            readings,
            key=lambda reading: abs(reading.score - 50),
            reverse=True,
        )
        symbols = {position.symbol for position in self.ledger.positions()}
        symbols.update(reading.symbol for reading in candidates)
        candles_by_symbol: dict[str, list[Candle]] = {}
        prices: dict[str, Candle] = {}
        for symbol in symbols:
            current_candles = self.bridge.candles(account, symbol, scan.timeframe, 80)
            if not current_candles:
                continue
            candles_by_symbol[symbol] = current_candles
            prices[symbol] = current_candles[-1]

        opportunities: list[MarketOpportunity] = []
        for rank, reading in enumerate(candidates, start=1):
            signal_candles = candles_by_symbol.get(reading.symbol)
            if not signal_candles:
                continue
            opportunity = self._to_opportunity(
                rank,
                reading,
                reading.price,
                signal_candles,
                strategy_label=strategy_label,
                stop_atr=stop_atr,
                target_r=target_r,
            )
            if opportunity is not None:
                opportunities.append(opportunity)

        market_scan = MarketScanResult(
            source=scan.source,
            timeframe=scan.timeframe,
            available_symbols=scan.available_symbols,
            scanned_symbols=scan.scanned_symbols,
            generated_at=scan.generated_at,
            disclaimer=(
                f"{strategy_label} uses verified MT5 prices for a separate paper-only ledger. "
                "It records simulated outcomes and lessons but never places live orders."
            ),
            opportunities=opportunities,
        )
        return self.ledger.process_cycle(
            market_scan,
            prices,
            account.id,
            now=scan.generated_at,
        )

    def _to_opportunity(
        self,
        rank: int,
        alert: ExtremeAlert | ExtremeReading,
        signal_price: float,
        candles: list[Candle],
        *,
        strategy_label: str = "Extreme scanner",
        stop_atr: float = 1.25,
        target_r: float = 1.5,
    ) -> MarketOpportunity | None:
        entry = candles[-1].close
        if not isfinite(entry) or entry <= 0:
            return None
        atr = self._atr(candles[-15:])
        if not isfinite(atr) or atr <= 0:
            return None
        risk_distance = max(atr * stop_atr, entry * 0.0005)
        direction = Direction.sell if alert.level == "upper_85" else Direction.buy
        if direction == Direction.buy:
            stop_loss = entry - risk_distance
            take_profit = entry + risk_distance * target_r
            impact: Literal["bullish", "bearish"] = "bullish"
        else:
            stop_loss = entry + risk_distance
            take_profit = entry - risk_distance * target_r
            impact = "bearish"
        if stop_loss <= 0 or take_profit <= 0:
            return None

        score = round(abs(alert.score - 50) * 2, 1)
        reasons = [
            SignalReason(
                "extreme",
                f"Composite score reached {alert.score:.2f} at the "
                f"{alert.level.replace('_', ' ')} threshold.",
                "neutral",
                0.35,
            ),
            SignalReason(
                "rsi",
                (
                    f"RSI(1) reached {alert.rsi1:.2f}; RSI(3) is "
                    f"{getattr(alert, 'rsi3', 50.0):.2f} for short-term confirmation."
                ),
                impact,
                0.2,
            ),
            SignalReason(
                "macd",
                (
                    f"MACD(5,6) is {alert.macd:.8g} with histogram "
                    f"{getattr(alert, 'macd_histogram', 0.0):.8g}."
                ),
                impact,
                0.25,
            ),
            SignalReason(
                "trend",
                (
                    f"Latest candle is {getattr(alert, 'candle_direction', 'unknown')}; "
                    "the entry requires a reversal trigger, not an extreme reading alone."
                ),
                impact,
                0.2,
            ),
        ]
        return MarketOpportunity(
            rank=rank,
            symbol=alert.symbol,
            description=f"{alert.symbol} {strategy_label} candidate",
            category=strategy_label,
            direction=direction,
            confidence=0.88,
            entry=entry,
            stop_loss=round(stop_loss, 8),
            take_profit=round(take_profit, 8),
            opportunity_score=score,
            estimated_move_pct=round(abs(take_profit - entry) / entry * 100, 3),
            spread_pct=0.0,
            market_active=True,
            quote_age_seconds=0,
            recommendation=alert.recommendation,
            reasons=reasons,
            signal_at=getattr(alert, "triggered_at", getattr(alert, "detected_at", None)),
            signal_price=signal_price,
            signal_level=alert.level,
            signal_recommendation=alert.recommendation,
        )

    @staticmethod
    def _is_confirmed(alert: ExtremeAlert) -> bool:
        if alert.level == "upper_85":
            return (
                alert.reversal_confirmed
                and alert.candle_direction == "bearish"
                and alert.rsi3 < 70
                and alert.rsi7 < 60
                and alert.momentum_pct < 0
                and alert.macd < alert.macd_signal
                and alert.ema_fast < alert.ema_slow
            )
        return (
            alert.reversal_confirmed
            and alert.candle_direction == "bullish"
            and alert.rsi3 > 30
            and alert.rsi7 > 40
            and alert.momentum_pct > 0
            and alert.macd > alert.macd_signal
            and alert.ema_fast > alert.ema_slow
        )

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
