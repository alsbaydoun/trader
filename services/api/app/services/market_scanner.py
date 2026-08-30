from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from threading import RLock

from app.domain.models import Direction, Signal, SignalReason
from app.services.accounts import BrokerAccountProfile
from app.services.mt5_bridge import MT5MarketSymbol, MT5ReadOnlyBridge
from app.services.strategy import SignalEngine


@dataclass(frozen=True)
class MarketOpportunity:
    rank: int
    symbol: str
    description: str
    category: str
    direction: Direction
    confidence: float
    entry: float
    stop_loss: float | None
    take_profit: float | None
    opportunity_score: float
    estimated_move_pct: float
    spread_pct: float
    market_active: bool
    quote_age_seconds: int | None
    recommendation: str
    reasons: list[SignalReason]
    signal_at: datetime | None = None
    signal_price: float | None = None
    signal_level: str | None = None
    signal_recommendation: str | None = None


@dataclass(frozen=True)
class MarketScanResult:
    source: str
    timeframe: str
    available_symbols: int
    scanned_symbols: int
    generated_at: datetime
    disclaimer: str
    opportunities: list[MarketOpportunity]


class MarketOpportunityScanner:
    def __init__(
        self,
        bridge: MT5ReadOnlyBridge,
        signal_engine: SignalEngine,
        cache_seconds: int = 60,
    ) -> None:
        self.bridge = bridge
        self.signal_engine = signal_engine
        self.cache_for = timedelta(seconds=cache_seconds)
        self._cache_key = ""
        self._cached_at: datetime | None = None
        self._cached: MarketScanResult | None = None
        self._lock = RLock()

    def scan(
        self,
        account: BrokerAccountProfile | None,
        timeframe: str,
        max_symbols: int,
        result_limit: int,
        force: bool = False,
    ) -> MarketScanResult:
        with self._lock:
            return self._scan_unlocked(
                account,
                timeframe,
                max_symbols,
                result_limit,
                force,
            )

    def _scan_unlocked(
        self,
        account: BrokerAccountProfile | None,
        timeframe: str,
        max_symbols: int,
        result_limit: int,
        force: bool,
    ) -> MarketScanResult:
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
            120,
            max_symbols,
        )
        metadata = {symbol.symbol: symbol for symbol in symbols}
        ranked: list[MarketOpportunity] = []
        for symbol, candles in candles_by_symbol.items():
            if len(candles) < self.signal_engine.definition().minimum_candles:
                continue
            signal = self.signal_engine.generate(candles)
            ranked.append(self._score(metadata[symbol], signal))

        ranked.sort(
            key=lambda item: (
                item.market_active,
                item.opportunity_score,
                item.confidence,
                -item.spread_pct,
            ),
            reverse=True,
        )
        opportunities = [replace(item, rank=index) for index, item in enumerate(ranked, start=1)]
        result = MarketScanResult(
            source="mt5" if symbols else "unavailable",
            timeframe=timeframe,
            available_symbols=len(symbols),
            scanned_symbols=len(candles_by_symbol),
            generated_at=now,
            disclaimer=(
                "Ranking estimates setup quality from current data. It does not predict or "
                "guarantee profit, and every candidate still requires risk approval."
            ),
            opportunities=opportunities,
        )
        self._cache_key = key
        self._cached_at = now
        self._cached = result
        return self._limited(result, result_limit)

    @staticmethod
    def _score(symbol: MT5MarketSymbol, signal: Signal) -> MarketOpportunity:
        direction = signal.direction
        confidence = signal.confidence
        entry = signal.entry
        take_profit = signal.take_profit
        reasons = signal.reasons
        mid = (symbol.bid + symbol.ask) / 2 if symbol.bid and symbol.ask else entry
        spread_pct = ((symbol.ask - symbol.bid) / mid * 100) if mid > 0 else 0.0
        estimated_move_pct = (
            abs(float(take_profit) - entry) / entry * 100 if take_profit and entry > 0 else 0.0
        )
        directional_factor = 1.0 if direction != Direction.hold else 0.42
        spread_penalty = min(0.3, spread_pct * 5)
        movement_quality = min(0.12, estimated_move_pct / 10)
        now = datetime.now(UTC)
        quote_age_seconds = (
            max(0, int((now - symbol.last_tick_at).total_seconds()))
            if symbol.last_tick_at
            else None
        )
        market_active = bool(
            symbol.bid > 0
            and symbol.ask > 0
            and quote_age_seconds is not None
            and quote_age_seconds <= 300
        )
        score = max(
            0.0,
            min(1.0, confidence * 0.82 * directional_factor + movement_quality - spread_penalty),
        )
        if not market_active:
            score *= 0.25
        score_value = round(score * 100, 1)
        if not market_active:
            recommendation = "Market inactive"
        elif direction != Direction.hold and score_value >= 62:
            recommendation = "Candidate"
        elif score_value >= 42:
            recommendation = "Watch"
        else:
            recommendation = "Low conviction"
        return MarketOpportunity(
            rank=0,
            symbol=symbol.symbol,
            description=symbol.description or symbol.symbol,
            category=symbol.category,
            direction=direction,
            confidence=confidence,
            entry=entry,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            opportunity_score=score_value,
            estimated_move_pct=round(estimated_move_pct, 3),
            spread_pct=round(spread_pct, 4),
            market_active=market_active,
            quote_age_seconds=quote_age_seconds,
            recommendation=recommendation,
            reasons=reasons[:3],
        )

    @staticmethod
    def _limited(result: MarketScanResult, limit: int) -> MarketScanResult:
        return MarketScanResult(
            source=result.source,
            timeframe=result.timeframe,
            available_symbols=result.available_symbols,
            scanned_symbols=result.scanned_symbols,
            generated_at=result.generated_at,
            disclaimer=result.disclaimer,
            opportunities=result.opportunities[:limit],
        )
