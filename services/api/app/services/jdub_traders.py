import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from threading import RLock
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.domain.models import Candle, Direction, Position, SignalReason
from app.services.accounts import BrokerAccountProfile
from app.services.market_scanner import MarketOpportunity, MarketScanResult
from app.services.mt5_bridge import MT5MarketSymbol, MT5ReadOnlyBridge
from app.services.paper_trading import PaperPortfolio, PaperTradingService


@dataclass(frozen=True)
class JdubSetup:
    session_date: str
    direction: Direction
    model: str
    trigger: Candle
    confirmation: Candle
    range_high: float
    range_low: float


@dataclass(frozen=True)
class JdubScanResult:
    market_scan: MarketScanResult
    prices: dict[str, Candle]


class JdubTradersService:
    """Paper implementation of the video's NY opening-range framework."""

    name = "Jdub Traders"
    timeframe = "1m"
    history_bars = 1000
    opening_range_minutes = 15
    entry_window_minutes = 90
    max_signal_age_minutes = 5
    target_r_multiple = 1.5
    new_york = ZoneInfo("America/New_York")

    def __init__(
        self,
        ledger: PaperTradingService,
        bridge: MT5ReadOnlyBridge,
        session_state_file: str,
    ) -> None:
        self.ledger = ledger
        self.bridge = bridge
        self.session_state_file = self._resolve_state_file(session_state_file)
        self._used_sessions: dict[str, str] = {}
        self._lock = RLock()
        self._load_sessions()

    @property
    def enabled(self) -> bool:
        return self.ledger.enabled

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
        with self._lock:
            self._used_sessions = {}
            self._save_sessions()
            return self.ledger.reset()

    def process_cycle(
        self,
        account: BrokerAccountProfile | None,
        max_symbols: int,
        result_limit: int = 50,
        force: bool = False,
    ) -> PaperPortfolio:
        result = self.scan(account, max_symbols, result_limit, force)
        if result.market_scan.source != "mt5" or account is None:
            self.ledger.record_error(
                "The Jdub Traders virtual cycle was skipped because verified MT5 market "
                "data is unavailable."
            )
            return self.ledger.snapshot()
        return self.ledger.process_cycle(
            result.market_scan,
            result.prices,
            account.id,
            now=result.market_scan.generated_at,
        )

    def scan(
        self,
        account: BrokerAccountProfile | None,
        max_symbols: int,
        result_limit: int = 50,
        force: bool = False,
        now: datetime | None = None,
    ) -> JdubScanResult:
        del force  # The bridge query is intentionally fresh for the time-sensitive paper loop.
        with self._lock:
            generated_at = now or datetime.now(UTC)
            if account is None:
                return JdubScanResult(
                    market_scan=self._empty_scan(generated_at, "unavailable"),
                    prices={},
                )

            symbols, candles_by_symbol = self.bridge.scan_market_candles(
                account,
                self.timeframe,
                self.history_bars,
                max_symbols,
            )
            metadata = {symbol.symbol: symbol for symbol in symbols}
            prices = {
                symbol: candles[-1]
                for symbol, candles in candles_by_symbol.items()
                if candles
            }
            candidates: list[tuple[MarketOpportunity, str]] = []
            for symbol, candles in candles_by_symbol.items():
                setup = self._setup(candles, generated_at)
                if setup is None or self._used_sessions.get(symbol) == setup.session_date:
                    continue
                opportunity = self._opportunity(setup, metadata.get(symbol), generated_at)
                if opportunity is not None:
                    candidates.append((opportunity, setup.session_date))

            candidates.sort(
                key=lambda item: (
                    item[0].market_active,
                    item[0].opportunity_score,
                    item[0].confidence,
                    -item[0].spread_pct,
                ),
                reverse=True,
            )
            opportunities: list[MarketOpportunity] = []
            for rank, (opportunity, session_date) in enumerate(candidates[:result_limit], start=1):
                opportunities.append(
                    MarketOpportunity(
                        **{**opportunity.__dict__, "rank": rank}
                    )
                )
                self._used_sessions[opportunity.symbol] = session_date
            if opportunities:
                self._save_sessions()

            return JdubScanResult(
                market_scan=MarketScanResult(
                    source="mt5" if symbols else "unavailable",
                    timeframe=self.timeframe,
                    available_symbols=len(symbols),
                    scanned_symbols=len(candles_by_symbol),
                    generated_at=generated_at,
                    disclaimer=(
                        "Jdub Traders is a paper-only mechanical interpretation of the linked "
                        "video: NY opening range, M5 confirmation, and M1 entry models. "
                        "It does not predict or guarantee profit and never places orders."
                    ),
                    opportunities=opportunities,
                ),
                prices=prices,
            )

    def _setup(self, candles: list[Candle], now: datetime) -> JdubSetup | None:
        ordered = sorted(candles, key=lambda candle: candle.ts)
        minimum_candles = self.opening_range_minutes + 6
        if len(ordered) < minimum_candles:
            return None
        latest = ordered[-1]
        session_date = latest.ts.astimezone(self.new_york).date()
        range_start = datetime.combine(
            session_date,
            time(hour=9, minute=30),
            tzinfo=self.new_york,
        ).astimezone(UTC)
        range_end = range_start + timedelta(minutes=self.opening_range_minutes)
        entry_end = range_start + timedelta(minutes=self.entry_window_minutes)
        if latest.ts < range_end or latest.ts >= entry_end:
            return None

        opening = [candle for candle in ordered if range_start <= candle.ts < range_end]
        if len(opening) != self.opening_range_minutes or not self._is_contiguous(opening):
            return None
        range_high = max(candle.high for candle in opening)
        range_low = min(candle.low for candle in opening)
        if range_high <= range_low:
            return None

        m5_bars = [
            candle
            for candle in self._aggregate_m5(ordered)
            if range_end <= candle.ts < entry_end
        ]
        setups: list[JdubSetup] = []
        for confirmation in m5_bars:
            after_confirmation = [
                candle
                for candle in ordered
                if confirmation.ts + timedelta(minutes=5) <= candle.ts <= latest.ts
            ]
            if confirmation.close > range_high and confirmation.close > confirmation.open:
                retest = next(
                    (
                        candle
                        for candle in after_confirmation
                        if candle.low <= range_high
                        and candle.close > range_high
                        and candle.close > candle.open
                    ),
                    None,
                )
                if retest is not None:
                    setups.append(
                        JdubSetup(
                            session_date=session_date.isoformat(),
                            direction=Direction.buy,
                            model="break-and-retest",
                            trigger=retest,
                            confirmation=confirmation,
                            range_high=range_high,
                            range_low=range_low,
                        )
                    )
                else:
                    breakout = next(
                        (
                            candle
                            for candle in after_confirmation
                            if candle.close > range_high and candle.close > candle.open
                        ),
                        None,
                    )
                    if breakout is not None:
                        setups.append(
                            JdubSetup(
                                session_date=session_date.isoformat(),
                                direction=Direction.buy,
                                model="breakout",
                                trigger=breakout,
                                confirmation=confirmation,
                                range_high=range_high,
                                range_low=range_low,
                            )
                        )
            elif confirmation.close < range_low and confirmation.close < confirmation.open:
                retest = next(
                    (
                        candle
                        for candle in after_confirmation
                        if candle.high >= range_low
                        and candle.close < range_low
                        and candle.close < candle.open
                    ),
                    None,
                )
                if retest is not None:
                    setups.append(
                        JdubSetup(
                            session_date=session_date.isoformat(),
                            direction=Direction.sell,
                            model="break-and-retest",
                            trigger=retest,
                            confirmation=confirmation,
                            range_high=range_high,
                            range_low=range_low,
                        )
                    )
                else:
                    breakout = next(
                        (
                            candle
                            for candle in after_confirmation
                            if candle.close < range_low and candle.close < candle.open
                        ),
                        None,
                    )
                    if breakout is not None:
                        setups.append(
                            JdubSetup(
                                session_date=session_date.isoformat(),
                                direction=Direction.sell,
                                model="breakout",
                                trigger=breakout,
                                confirmation=confirmation,
                                range_high=range_high,
                                range_low=range_low,
                            )
                        )

            if confirmation.high > range_high and confirmation.close < range_high:
                reversal = next(
                    (
                        candle
                        for candle in after_confirmation
                        if candle.close < range_high and candle.close < candle.open
                    ),
                    None,
                )
                if reversal is not None:
                    setups.append(
                        JdubSetup(
                            session_date=session_date.isoformat(),
                            direction=Direction.sell,
                            model="reversal",
                            trigger=reversal,
                            confirmation=confirmation,
                            range_high=range_high,
                            range_low=range_low,
                        )
                    )
            if confirmation.low < range_low and confirmation.close > range_low:
                reversal = next(
                    (
                        candle
                        for candle in after_confirmation
                        if candle.close > range_low and candle.close > candle.open
                    ),
                    None,
                )
                if reversal is not None:
                    setups.append(
                        JdubSetup(
                            session_date=session_date.isoformat(),
                            direction=Direction.buy,
                            model="reversal",
                            trigger=reversal,
                            confirmation=confirmation,
                            range_high=range_high,
                            range_low=range_low,
                        )
                    )

        if not setups:
            return None
        recent = [
            setup
            for setup in setups
            if now - setup.trigger.ts <= timedelta(minutes=self.max_signal_age_minutes)
        ]
        return max(recent, key=lambda setup: setup.trigger.ts) if recent else None

    def _opportunity(
        self,
        setup: JdubSetup,
        metadata: MT5MarketSymbol | None,
        now: datetime,
    ) -> MarketOpportunity | None:
        entry = setup.trigger.close
        range_size = setup.range_high - setup.range_low
        if entry <= 0 or range_size <= 0:
            return None
        if metadata is None:
            return None
        quote_age_seconds = (
            max(0, int((now - metadata.last_tick_at).total_seconds()))
            if metadata.last_tick_at
            else None
        )
        market_active = bool(
            metadata.bid > 0
            and metadata.ask > 0
            and quote_age_seconds is not None
            and quote_age_seconds <= 300
        )
        midpoint = (metadata.bid + metadata.ask) / 2 if metadata.bid and metadata.ask else entry
        spread_pct = (metadata.ask - metadata.bid) / midpoint * 100 if midpoint > 0 else 0.0
        buffer = max(range_size * 0.05, entry * 0.0001)
        impact: Literal["bullish", "bearish"]
        if setup.direction == Direction.buy:
            anchor = setup.trigger.low if setup.model != "breakout" else setup.range_high
            stop_loss = min(entry - range_size * 0.15, anchor - buffer)
            risk_distance = entry - stop_loss
            take_profit = entry + risk_distance * self.target_r_multiple
            impact = "bullish"
        else:
            anchor = setup.trigger.high if setup.model != "breakout" else setup.range_low
            stop_loss = max(entry + range_size * 0.15, anchor + buffer)
            risk_distance = stop_loss - entry
            take_profit = entry - risk_distance * self.target_r_multiple
            impact = "bearish"
        if stop_loss <= 0 or take_profit <= 0 or risk_distance <= 0:
            return None

        model_score = {"break-and-retest": 84.0, "reversal": 76.0, "breakout": 70.0}[setup.model]
        score = round(max(0.0, min(100.0, model_score - min(15.0, spread_pct * 200))), 1)
        model_label = setup.model.replace("-", " ")
        return MarketOpportunity(
            rank=0,
            symbol=setup.trigger.symbol,
            description=f"{setup.trigger.symbol} {self.name} candidate",
            category=self.name,
            direction=setup.direction,
            confidence={"break-and-retest": 0.84, "reversal": 0.78, "breakout": 0.72}[setup.model],
            entry=entry,
            stop_loss=round(stop_loss, 8),
            take_profit=round(take_profit, 8),
            opportunity_score=score,
            estimated_move_pct=round(abs(take_profit - entry) / entry * 100, 3),
            spread_pct=round(spread_pct, 4),
            market_active=market_active,
            quote_age_seconds=quote_age_seconds,
            recommendation=(
                f"Paper {setup.direction.value} candidate: NY opening-range {model_label}."
            ),
            reasons=[
                SignalReason(
                    "opening_range",
                    (
                        f"New York opening range 09:30-09:45 ET: high {setup.range_high:.8g}, "
                        f"low {setup.range_low:.8g}."
                    ),
                    "neutral",
                    0.4,
                ),
                SignalReason(
                    "confirmation",
                    (
                        "Completed 5-minute candle closed "
                        f"{'above' if setup.direction == Direction.buy else 'below'} "
                        "the opening range."
                    ),
                    impact,
                    0.3,
                ),
                SignalReason(
                    "entry_model",
                    f"1-minute {model_label} trigger confirmed at {setup.trigger.close:.8g}.",
                    impact,
                    0.2,
                ),
                SignalReason(
                    "risk",
                    (
                        f"Virtual stop is {stop_loss:.8g}; target is {take_profit:.8g} at "
                        f"{self.target_r_multiple:.2f}R. Stop assumptions are explicit because "
                        "the video does not specify one universal placement rule."
                    ),
                    "risk",
                    0.1,
                ),
            ],
            signal_at=setup.trigger.ts,
            signal_price=setup.trigger.close,
            signal_level=f"jdub-{setup.session_date}-{setup.model}",
            signal_recommendation=(
                "Faithful paper interpretation of the linked Jdub Trades opening-range video."
            ),
        )

    @staticmethod
    def _aggregate_m5(candles: list[Candle]) -> list[Candle]:
        groups: dict[datetime, list[Candle]] = {}
        for candle in candles:
            bucket = candle.ts.replace(
                minute=candle.ts.minute - candle.ts.minute % 5,
                second=0,
                microsecond=0,
            )
            groups.setdefault(bucket, []).append(candle)
        completed: list[Candle] = []
        for bucket, members in sorted(groups.items()):
            ordered = sorted(members, key=lambda candle: candle.ts)
            if len(ordered) != 5 or not JdubTradersService._is_contiguous(ordered):
                continue
            completed.append(
                Candle(
                    symbol=ordered[-1].symbol,
                    timeframe="5m",
                    ts=bucket,
                    open=ordered[0].open,
                    high=max(candle.high for candle in ordered),
                    low=min(candle.low for candle in ordered),
                    close=ordered[-1].close,
                    volume=sum(candle.volume for candle in ordered),
                    source=ordered[-1].source,
                )
            )
        return completed

    @staticmethod
    def _is_contiguous(candles: list[Candle]) -> bool:
        return all(
            current.ts - previous.ts == timedelta(minutes=1)
            for previous, current in zip(candles[:-1], candles[1:], strict=True)
        )

    @staticmethod
    def _empty_scan(generated_at: datetime, source: str) -> MarketScanResult:
        return MarketScanResult(
            source=source,
            timeframe="1m",
            available_symbols=0,
            scanned_symbols=0,
            generated_at=generated_at,
            disclaimer="Jdub Traders is waiting for verified MT5 data.",
            opportunities=[],
        )

    def _load_sessions(self) -> None:
        if not self.session_state_file.is_file():
            return
        try:
            payload = json.loads(self.session_state_file.read_text(encoding="utf-8"))
            raw_sessions = payload.get("used_sessions", {}) if isinstance(payload, dict) else {}
            if isinstance(raw_sessions, dict):
                self._used_sessions = {
                    str(symbol): str(session)
                    for symbol, session in raw_sessions.items()
                    if str(symbol) and str(session)
                }
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            self._used_sessions = {}

    def _save_sessions(self) -> None:
        self.session_state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.session_state_file.with_suffix(
            f"{self.session_state_file.suffix}.tmp"
        )
        payload: dict[str, Any] = {"version": 1, "used_sessions": self._used_sessions}
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.session_state_file)
        except OSError:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _resolve_state_file(state_file: str) -> Path:
        configured = Path(state_file)
        if configured.is_absolute():
            return configured
        api_directory = Path(__file__).resolve().parents[2]
        return (api_directory / configured).resolve()
