import json
import os
import shutil
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any, Literal
from uuid import uuid4

from app.domain.models import Candle, Direction, OrderRequest, Position
from app.services.market_scanner import MarketOpportunity, MarketScanResult

PaperTradeStatus = Literal["open", "closed"]
PaperExitReason = Literal[
    "stop_loss",
    "take_profit",
    "signal_reversal",
    "time_limit",
    "operator",
]
PaperDecisionAction = Literal["cycle", "opened", "closed", "error", "control"]


@dataclass
class PaperTrade:
    id: str
    symbol: str
    direction: Direction
    timeframe: str
    status: PaperTradeStatus
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: float | None
    take_profit: float | None
    risk_amount: float
    entry_fee: float
    exit_fee: float
    gross_pnl: float
    net_pnl: float
    unrealized_pnl: float
    return_pct: float
    r_multiple: float
    confidence: float
    opportunity_score: float
    scan_rank: int
    reasons: list[str]
    source: str
    source_account_id: str
    opened_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    exit_price: float | None = None
    exit_reason: PaperExitReason | None = None
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    factor_categories: list[str] = field(default_factory=list)
    learning_adjustment: float = 0.0
    learned_score: float = 0.0
    signal_at: datetime | None = None
    signal_price: float | None = None
    signal_level: str | None = None
    signal_recommendation: str | None = None


@dataclass
class PaperDecision:
    id: str
    cycle_id: str
    created_at: datetime
    action: PaperDecisionAction
    outcome: str
    reason: str
    symbol: str | None = None
    trade_id: str | None = None
    signal_direction: Direction | None = None
    opportunity_score: float | None = None


@dataclass
class PaperEquityPoint:
    timestamp: datetime
    equity: float
    balance: float
    unrealized_pnl: float


@dataclass
class PaperFactorPerformance:
    factor: str
    samples: int
    wins: int
    losses: int
    win_rate: float
    average_r_multiple: float


@dataclass
class PaperDailyReport:
    date: str
    opening_balance: float
    closing_balance: float
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    winning_amount: float
    losing_amount: float
    winning_pct: float
    losing_pct: float
    net_pnl: float
    net_return_pct: float
    fees_paid: float
    profit_factor: float | None


@dataclass
class PaperLearningLesson:
    observed_at: datetime
    trade_id: str
    symbol: str
    direction: Direction
    exit_reason: str
    r_multiple: float
    factors: list[str]
    fault: str
    future_action: str


@dataclass
class PaperLearningProfile:
    enabled: bool
    mode: str
    observations: int
    wins: int
    losses: int
    last_updated_at: datetime | None
    last_fault: str
    recommendation: str
    factor_performance: list[PaperFactorPerformance]
    future_plan: str
    lessons: list[PaperLearningLesson]


@dataclass
class PaperPersistenceStatus:
    storage: str
    state_version: int
    status: str
    last_saved_at: datetime | None
    backup_available: bool


@dataclass
class PaperEngineStatus:
    enabled: bool
    virtual_only: bool
    timeframe: str
    minimum_opportunity_score: float
    max_open_positions: int
    risk_per_trade_pct: float
    cycle_interval_seconds: int
    cycle_count: int
    last_cycle_at: datetime | None
    last_scan_at: datetime | None
    next_cycle_at: datetime | None
    last_error: str
    market_source: str
    source_account_id: str
    scanned_symbols: int
    eligible_candidates: int
    opened_last_cycle: int
    closed_last_cycle: int


@dataclass
class PaperMetrics:
    starting_balance: float
    balance: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_return_pct: float
    open_positions: int
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float | None
    average_r_multiple: float
    max_drawdown_pct: float
    open_risk_amount: float
    fees_paid: float
    best_trade: float | None
    worst_trade: float | None


@dataclass
class PaperPortfolio:
    engine: PaperEngineStatus
    metrics: PaperMetrics
    open_positions: list[PaperTrade]
    closed_trades: list[PaperTrade]
    decisions: list[PaperDecision]
    equity_curve: list[PaperEquityPoint]
    learning: PaperLearningProfile
    daily_reports: list[PaperDailyReport]
    persistence: PaperPersistenceStatus
    disclaimer: str


class PaperTradingService:
    """Persistent virtual portfolio. It never calls a broker order function."""

    def __init__(
        self,
        state_file: str,
        *,
        enabled: bool,
        starting_balance: float,
        risk_per_trade_pct: float,
        max_open_positions: int,
        minimum_opportunity_score: float,
        commission_bps: float,
        slippage_bps: float,
        cycle_interval_seconds: int,
        max_position_minutes: int,
        adaptive_learning_enabled: bool = True,
        learning_min_samples: int = 8,
        trade_source: str = "mt5-virtual",
    ) -> None:
        self.state_file = self._resolve_state_file(state_file)
        self.backup_file = self.state_file.with_suffix(f"{self.state_file.suffix}.bak")
        self.starting_balance = starting_balance
        self.enabled = enabled
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_open_positions = max_open_positions
        self.minimum_opportunity_score = minimum_opportunity_score
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps
        self.cycle_interval_seconds = cycle_interval_seconds
        self.max_position_minutes = max_position_minutes
        self.adaptive_learning_enabled = adaptive_learning_enabled
        self.learning_min_samples = learning_min_samples
        self.trade_source = trade_source
        self.timeframe = "1m"
        self.trades: list[PaperTrade] = []
        self.decisions: list[PaperDecision] = []
        self.equity_curve: list[PaperEquityPoint] = []
        self.cycle_count = 0
        self.last_cycle_at: datetime | None = None
        self.last_scan_at: datetime | None = None
        self.last_error = ""
        self.market_source = "waiting"
        self.source_account_id = ""
        self.scanned_symbols = 0
        self.eligible_candidates = 0
        self.opened_last_cycle = 0
        self.closed_last_cycle = 0
        self.learning_observations = 0
        self.learning_wins = 0
        self.learning_losses = 0
        self.learning_last_updated_at: datetime | None = None
        self.learning_last_fault = ""
        self.learning_stats: dict[str, dict[str, float]] = {}
        self.persistence_status = "new"
        self.last_saved_at: datetime | None = None
        self._lock = RLock()
        self._load()

    def positions(self) -> list[Position]:
        with self._lock:
            return [
                Position(
                    id=trade.id,
                    symbol=trade.symbol,
                    direction=trade.direction,
                    volume=trade.quantity,
                    entry=trade.entry_price,
                    stop_loss=trade.stop_loss,
                    take_profit=trade.take_profit,
                    opened_at=trade.opened_at,
                )
                for trade in self._open_trades()
            ]

    def place_order(self, order: OrderRequest) -> Position:
        if order.direction == Direction.hold:
            raise ValueError("Hold signals cannot be opened in the paper portfolio.")
        with self._lock:
            now = datetime.now(UTC)
            risk_distance = abs(order.entry - float(order.stop_loss or order.entry))
            trade = PaperTrade(
                id=f"paper-{uuid4().hex[:12]}",
                symbol=order.symbol,
                direction=order.direction,
                timeframe=self.timeframe,
                status="open",
                quantity=order.volume,
                entry_price=order.entry,
                current_price=order.entry,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                risk_amount=round(risk_distance * order.volume, 2),
                entry_fee=self._fee(order.entry, order.volume),
                exit_fee=0.0,
                gross_pnl=0.0,
                net_pnl=0.0,
                unrealized_pnl=0.0,
                return_pct=0.0,
                r_multiple=0.0,
                confidence=0.0,
                opportunity_score=0.0,
                scan_rank=0,
                reasons=["Manual paper order submitted through the API."],
                source="manual",
                source_account_id=self.source_account_id,
                opened_at=now,
                updated_at=now,
            )
            self.trades.append(trade)
            self._decision(
                cycle_id="manual",
                action="opened",
                outcome="accepted",
                reason="Manual order opened in the virtual portfolio only.",
                symbol=trade.symbol,
                trade=trade,
            )
            self._save()
            return self.positions()[-1]

    def process_cycle(
        self,
        scan: MarketScanResult,
        prices: dict[str, Candle],
        source_account_id: str,
        now: datetime | None = None,
    ) -> PaperPortfolio:
        with self._lock:
            cycle_time = now or datetime.now(UTC)
            cycle_id = f"cycle-{uuid4().hex[:10]}"
            self.timeframe = scan.timeframe
            self.market_source = scan.source
            self.source_account_id = source_account_id
            self.scanned_symbols = scan.scanned_symbols
            self.last_scan_at = scan.generated_at
            self.opened_last_cycle = 0
            self.closed_last_cycle = 0
            by_symbol = {item.symbol: item for item in scan.opportunities}

            closed_symbols: set[str] = set()
            for trade in list(self._open_trades()):
                candle = prices.get(trade.symbol)
                if candle is None:
                    continue
                self._mark_trade(trade, candle)
                exit_price, exit_reason = self._exit_trigger(trade, candle, cycle_time)
                current_opportunity = by_symbol.get(trade.symbol)
                if (
                    exit_price is None
                    and current_opportunity is not None
                    and current_opportunity.direction not in {Direction.hold, trade.direction}
                ):
                    exit_price = candle.close
                    exit_reason = "signal_reversal"
                if exit_price is not None and exit_reason is not None:
                    self._close_trade(trade, exit_price, exit_reason, cycle_time, cycle_id)
                    closed_symbols.add(trade.symbol)

            actionable: list[tuple[MarketOpportunity, float]] = []
            learning_blocked = 0
            for item in scan.opportunities:
                if not item.market_active or item.direction == Direction.hold:
                    continue
                learning_adjustment = self._learning_adjustment(item)
                learned_score = max(0.0, min(100.0, item.opportunity_score + learning_adjustment))
                if item.opportunity_score < self.minimum_opportunity_score:
                    continue
                if (
                    self.adaptive_learning_enabled
                    and self.learning_observations >= self.learning_min_samples
                    and learned_score < max(35.0, self.minimum_opportunity_score)
                ):
                    learning_blocked += 1
                    continue
                actionable.append((item, learning_adjustment))
            self.eligible_candidates = len(actionable)
            open_symbols = {trade.symbol for trade in self._open_trades()}
            blocked_by_limit = 0
            for opportunity, learning_adjustment in actionable:
                if opportunity.symbol in open_symbols or opportunity.symbol in closed_symbols:
                    continue
                if len(open_symbols) >= self.max_open_positions:
                    blocked_by_limit += 1
                    continue
                new_trade = self._open_opportunity(
                    opportunity,
                    source_account_id,
                    cycle_time,
                    learning_adjustment,
                )
                if new_trade is None:
                    continue
                open_symbols.add(new_trade.symbol)
                self.opened_last_cycle += 1
                self._decision(
                    cycle_id=cycle_id,
                    action="opened",
                    outcome="accepted",
                    reason=(
                        "Actionable strategy signal passed the virtual portfolio limits. "
                        f"Risk budget {new_trade.risk_amount:.2f}; estimated entry fee "
                        f"{new_trade.entry_fee:.2f}."
                    ),
                    symbol=new_trade.symbol,
                    trade=new_trade,
                    opportunity=opportunity,
                )

            self.cycle_count += 1
            self.last_cycle_at = cycle_time
            self.last_error = ""
            self._decision(
                cycle_id=cycle_id,
                action="cycle",
                outcome="completed",
                reason=(
                    f"Scanned {scan.scanned_symbols} instruments; found {len(actionable)} "
                    f"actionable signals; opened {self.opened_last_cycle}; closed "
                    f"{self.closed_last_cycle}; {blocked_by_limit} blocked by the virtual "
                    f"position limit; {learning_blocked} filtered by the paper learning overlay."
                ),
            )
            self._append_equity_point(cycle_time)
            self._trim()
            self._save()
            return self.snapshot()

    def record_error(self, message: str) -> None:
        with self._lock:
            self.last_error = message
            self._decision(
                cycle_id=f"cycle-{uuid4().hex[:10]}",
                action="error",
                outcome="failed",
                reason=message,
            )
            self._save()

    def update_control(
        self,
        *,
        enabled: bool | None = None,
        timeframe: str | None = None,
        minimum_opportunity_score: float | None = None,
        max_open_positions: int | None = None,
    ) -> PaperPortfolio:
        with self._lock:
            if enabled is not None:
                self.enabled = enabled
            if timeframe is not None:
                self.timeframe = timeframe
            if minimum_opportunity_score is not None:
                self.minimum_opportunity_score = minimum_opportunity_score
            if max_open_positions is not None:
                self.max_open_positions = max_open_positions
            self._decision(
                cycle_id="control",
                action="control",
                outcome="updated",
                reason=(
                    f"Virtual engine {'running' if self.enabled else 'paused'}; timeframe "
                    f"{self.timeframe}; minimum score {self.minimum_opportunity_score:.1f}; "
                    f"maximum {self.max_open_positions} open positions."
                ),
            )
            self._save()
            return self.snapshot()

    def close_trade(self, trade_id: str, price: float) -> PaperPortfolio:
        with self._lock:
            trade = next(
                (item for item in self.trades if item.id == trade_id and item.status == "open"),
                None,
            )
            if trade is None:
                raise KeyError(trade_id)
            self._close_trade(
                trade,
                price,
                "operator",
                datetime.now(UTC),
                "operator",
            )
            self._append_equity_point(datetime.now(UTC))
            self._save()
            return self.snapshot()

    def reset(self) -> PaperPortfolio:
        with self._lock:
            self.trades = []
            self.decisions = []
            self.equity_curve = []
            self.cycle_count = 0
            self.last_cycle_at = None
            self.last_scan_at = None
            self.last_error = ""
            self.market_source = "waiting"
            self.scanned_symbols = 0
            self.eligible_candidates = 0
            self.opened_last_cycle = 0
            self.closed_last_cycle = 0
            self.learning_observations = 0
            self.learning_wins = 0
            self.learning_losses = 0
            self.learning_last_updated_at = None
            self.learning_last_fault = ""
            self.learning_stats = {}
            self._decision(
                cycle_id="control",
                action="control",
                outcome="reset",
                reason="Virtual portfolio reset to its starting balance.",
            )
            self._save()
            return self.snapshot()

    def snapshot(self) -> PaperPortfolio:
        with self._lock:
            open_positions = sorted(self._open_trades(), key=lambda item: item.opened_at)
            closed_trades = sorted(
                (trade for trade in self.trades if trade.status == "closed"),
                key=lambda item: item.closed_at or item.updated_at,
                reverse=True,
            )
            metrics = self._metrics(open_positions, closed_trades)
            next_cycle_at = (
                self.last_cycle_at + timedelta(seconds=self.cycle_interval_seconds)
                if self.enabled and self.last_cycle_at
                else None
            )
            engine = PaperEngineStatus(
                enabled=self.enabled,
                virtual_only=True,
                timeframe=self.timeframe,
                minimum_opportunity_score=self.minimum_opportunity_score,
                max_open_positions=self.max_open_positions,
                risk_per_trade_pct=self.risk_per_trade_pct,
                cycle_interval_seconds=self.cycle_interval_seconds,
                cycle_count=self.cycle_count,
                last_cycle_at=self.last_cycle_at,
                last_scan_at=self.last_scan_at,
                next_cycle_at=next_cycle_at,
                last_error=self.last_error,
                market_source=self.market_source,
                source_account_id=self.source_account_id,
                scanned_symbols=self.scanned_symbols,
                eligible_candidates=self.eligible_candidates,
                opened_last_cycle=self.opened_last_cycle,
                closed_last_cycle=self.closed_last_cycle,
            )
            learning = self._learning_profile(closed_trades)
            daily_reports = self._daily_reports(self._closed_trades())
            persistence = PaperPersistenceStatus(
                storage="Local server ledger",
                state_version=2,
                status=self.persistence_status,
                last_saved_at=self.last_saved_at,
                backup_available=self.backup_file.is_file(),
            )
            return PaperPortfolio(
                engine=engine,
                metrics=metrics,
                open_positions=open_positions,
                closed_trades=closed_trades[:500],
                decisions=list(reversed(self.decisions[-500:])),
                equity_curve=self.equity_curve[-1000:],
                learning=learning,
                daily_reports=daily_reports,
                persistence=persistence,
                disclaimer=(
                    "Virtual results use observed prices plus configured simulation costs. They "
                    "do not place MT5 orders, use real money, or predict future live performance."
                ),
            )

    def _open_opportunity(
        self,
        opportunity: MarketOpportunity,
        source_account_id: str,
        now: datetime,
        learning_adjustment: float = 0.0,
    ) -> PaperTrade | None:
        if opportunity.stop_loss is None or opportunity.take_profit is None:
            return None
        slip = opportunity.entry * (self.slippage_bps / 10_000)
        entry = (
            opportunity.entry + slip
            if opportunity.direction == Direction.buy
            else opportunity.entry - slip
        )
        risk_distance = abs(entry - opportunity.stop_loss)
        if risk_distance <= 0:
            return None
        equity = self._metrics(self._open_trades(), self._closed_trades()).equity
        risk_amount = max(0.01, equity * (self.risk_per_trade_pct / 100))
        quantity = risk_amount / risk_distance
        trade = PaperTrade(
            id=f"paper-{uuid4().hex[:12]}",
            symbol=opportunity.symbol,
            direction=opportunity.direction,
            timeframe=self.timeframe,
            status="open",
            quantity=round(quantity, 8),
            entry_price=round(entry, 8),
            current_price=round(entry, 8),
            stop_loss=opportunity.stop_loss,
            take_profit=opportunity.take_profit,
            risk_amount=round(risk_amount, 2),
            entry_fee=self._fee(entry, quantity),
            exit_fee=0.0,
            gross_pnl=0.0,
            net_pnl=0.0,
            unrealized_pnl=0.0,
            return_pct=0.0,
            r_multiple=0.0,
            confidence=opportunity.confidence,
            opportunity_score=opportunity.opportunity_score,
            scan_rank=opportunity.rank,
            reasons=[reason.message for reason in opportunity.reasons],
            source=self.trade_source,
            source_account_id=source_account_id,
            opened_at=now,
            updated_at=now,
            factor_categories=[
                reason.category for reason in opportunity.reasons if reason.category != "risk"
            ],
            learning_adjustment=round(learning_adjustment, 2),
            learned_score=round(
                max(0.0, min(100.0, opportunity.opportunity_score + learning_adjustment)), 1
            ),
            signal_at=opportunity.signal_at or now,
            signal_price=opportunity.signal_price or opportunity.entry,
            signal_level=opportunity.signal_level,
            signal_recommendation=opportunity.signal_recommendation or opportunity.recommendation,
        )
        self.trades.append(trade)
        return trade

    def _mark_trade(self, trade: PaperTrade, candle: Candle) -> None:
        trade.current_price = candle.close
        trade.updated_at = datetime.now(UTC)
        favorable_price = candle.high if trade.direction == Direction.buy else candle.low
        adverse_price = candle.low if trade.direction == Direction.buy else candle.high
        favorable = self._gross_pnl(trade, favorable_price)
        adverse = self._gross_pnl(trade, adverse_price)
        trade.max_favorable_excursion = round(max(trade.max_favorable_excursion, favorable), 2)
        trade.max_adverse_excursion = round(min(trade.max_adverse_excursion, adverse), 2)
        estimated_exit_fee = self._fee(candle.close, trade.quantity)
        gross = self._gross_pnl(trade, candle.close)
        trade.unrealized_pnl = round(gross - trade.entry_fee - estimated_exit_fee, 2)
        notional = abs(trade.entry_price * trade.quantity)
        trade.return_pct = round(trade.unrealized_pnl / notional * 100, 3) if notional else 0.0
        trade.r_multiple = (
            round(trade.unrealized_pnl / trade.risk_amount, 3) if trade.risk_amount else 0.0
        )

    def _exit_trigger(
        self,
        trade: PaperTrade,
        candle: Candle,
        now: datetime,
    ) -> tuple[float | None, PaperExitReason | None]:
        if trade.direction == Direction.buy:
            if trade.stop_loss is not None and candle.low <= trade.stop_loss:
                return trade.stop_loss, "stop_loss"
            if trade.take_profit is not None and candle.high >= trade.take_profit:
                return trade.take_profit, "take_profit"
        else:
            if trade.stop_loss is not None and candle.high >= trade.stop_loss:
                return trade.stop_loss, "stop_loss"
            if trade.take_profit is not None and candle.low <= trade.take_profit:
                return trade.take_profit, "take_profit"
        if now - trade.opened_at >= timedelta(minutes=self.max_position_minutes):
            return candle.close, "time_limit"
        return None, None

    def _close_trade(
        self,
        trade: PaperTrade,
        exit_price: float,
        exit_reason: PaperExitReason,
        now: datetime,
        cycle_id: str,
    ) -> None:
        trade.status = "closed"
        trade.current_price = exit_price
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.closed_at = now
        trade.updated_at = now
        trade.exit_fee = self._fee(exit_price, trade.quantity)
        trade.gross_pnl = round(self._gross_pnl(trade, exit_price), 2)
        trade.net_pnl = round(trade.gross_pnl - trade.entry_fee - trade.exit_fee, 2)
        trade.unrealized_pnl = 0.0
        notional = abs(trade.entry_price * trade.quantity)
        trade.return_pct = round(trade.net_pnl / notional * 100, 3) if notional else 0.0
        trade.r_multiple = round(trade.net_pnl / trade.risk_amount, 3) if trade.risk_amount else 0.0
        self.closed_last_cycle += 1
        learning_note = self._record_learning_outcome(trade)
        self._decision(
            cycle_id=cycle_id,
            action="closed",
            outcome="profit" if trade.net_pnl > 0 else "loss",
            reason=(
                f"Closed by {exit_reason.replace('_', ' ')} at {exit_price:.8g}. "
                f"Net virtual result {trade.net_pnl:.2f} ({trade.r_multiple:.2f}R). "
                f"{learning_note}"
            ),
            symbol=trade.symbol,
            trade=trade,
        )

    def _metrics(
        self,
        open_positions: list[PaperTrade],
        closed_trades: list[PaperTrade],
    ) -> PaperMetrics:
        realized = sum(trade.net_pnl for trade in closed_trades)
        unrealized = sum(trade.unrealized_pnl for trade in open_positions)
        balance = self.starting_balance + realized
        equity = balance + unrealized
        winners = [trade for trade in closed_trades if trade.net_pnl > 0]
        losers = [trade for trade in closed_trades if trade.net_pnl < 0]
        gross_profit = sum(trade.net_pnl for trade in winners)
        gross_loss = abs(sum(trade.net_pnl for trade in losers))
        profit_factor = round(gross_profit / gross_loss, 3) if gross_loss > 0 else None
        average_r = (
            sum(trade.r_multiple for trade in closed_trades) / len(closed_trades)
            if closed_trades
            else 0.0
        )
        drawdown = self._max_drawdown_pct(equity)
        results = [trade.net_pnl for trade in closed_trades]
        return PaperMetrics(
            starting_balance=round(self.starting_balance, 2),
            balance=round(balance, 2),
            equity=round(equity, 2),
            realized_pnl=round(realized, 2),
            unrealized_pnl=round(unrealized, 2),
            total_return_pct=round((equity / self.starting_balance - 1) * 100, 3),
            open_positions=len(open_positions),
            closed_trades=len(closed_trades),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate=round(len(winners) / len(closed_trades) * 100, 1) if closed_trades else 0.0,
            profit_factor=profit_factor,
            average_r_multiple=round(average_r, 3),
            max_drawdown_pct=round(drawdown, 3),
            open_risk_amount=round(sum(trade.risk_amount for trade in open_positions), 2),
            fees_paid=round(
                sum(trade.entry_fee + trade.exit_fee for trade in closed_trades)
                + sum(trade.entry_fee for trade in open_positions),
                2,
            ),
            best_trade=round(max(results), 2) if results else None,
            worst_trade=round(min(results), 2) if results else None,
        )

    def _append_equity_point(self, timestamp: datetime) -> None:
        metrics = self._metrics(self._open_trades(), self._closed_trades())
        self.equity_curve.append(
            PaperEquityPoint(
                timestamp=timestamp,
                equity=metrics.equity,
                balance=metrics.balance,
                unrealized_pnl=metrics.unrealized_pnl,
            )
        )

    def _max_drawdown_pct(self, current_equity: float) -> float:
        values = [point.equity for point in self.equity_curve] + [current_equity]
        peak = self.starting_balance
        maximum = 0.0
        for value in values:
            peak = max(peak, value)
            if peak > 0:
                maximum = max(maximum, (peak - value) / peak * 100)
        return maximum

    def _decision(
        self,
        *,
        cycle_id: str,
        action: PaperDecisionAction,
        outcome: str,
        reason: str,
        symbol: str | None = None,
        trade: PaperTrade | None = None,
        opportunity: MarketOpportunity | None = None,
    ) -> None:
        self.decisions.append(
            PaperDecision(
                id=f"decision-{uuid4().hex[:12]}",
                cycle_id=cycle_id,
                created_at=datetime.now(UTC),
                action=action,
                outcome=outcome,
                reason=reason,
                symbol=symbol,
                trade_id=trade.id if trade else None,
                signal_direction=(
                    opportunity.direction
                    if opportunity
                    else trade.direction if trade else None
                ),
                opportunity_score=(
                    opportunity.opportunity_score
                    if opportunity
                    else trade.opportunity_score if trade else None
                ),
            )
        )

    def _fee(self, price: float, quantity: float) -> float:
        return round(abs(price * quantity) * (self.commission_bps / 10_000), 2)

    @staticmethod
    def _gross_pnl(trade: PaperTrade, price: float) -> float:
        multiplier = 1 if trade.direction == Direction.buy else -1
        return (price - trade.entry_price) * trade.quantity * multiplier

    def _open_trades(self) -> list[PaperTrade]:
        return [trade for trade in self.trades if trade.status == "open"]

    def _closed_trades(self) -> list[PaperTrade]:
        return [trade for trade in self.trades if trade.status == "closed"]

    def _learning_adjustment(self, opportunity: MarketOpportunity) -> float:
        if not self.adaptive_learning_enabled:
            return 0.0
        adjustments: list[float] = []
        for reason in opportunity.reasons:
            stats = self.learning_stats.get(reason.category)
            samples = int(stats.get("samples", 0)) if stats else 0
            if not stats or samples < self.learning_min_samples:
                continue
            wins = stats.get("wins", 0.0)
            reliability = (wins + 1.0) / (samples + 2.0)
            # Reliability belongs to the factor, not the trade direction. A bearish
            # factor can be useful for sells just as a bullish factor can be useful
            # for buys, so do not invert the learned evidence for sell candidates.
            adjustments.append((reliability - 0.5) * 10.0)
        if not adjustments:
            return 0.0
        return round(max(-10.0, min(10.0, sum(adjustments) / len(adjustments))), 2)

    def _record_learning_outcome(self, trade: PaperTrade) -> str:
        self.learning_observations += 1
        if trade.net_pnl > 0:
            self.learning_wins += 1
        else:
            self.learning_losses += 1
        self.learning_last_updated_at = datetime.now(UTC)
        factors = trade.factor_categories or ["manual"]
        for factor in factors:
            stats = self.learning_stats.setdefault(
                factor,
                {"samples": 0.0, "wins": 0.0, "losses": 0.0, "r_total": 0.0},
            )
            stats["samples"] += 1
            stats["r_total"] += trade.r_multiple
            if trade.net_pnl > 0:
                stats["wins"] += 1
            else:
                stats["losses"] += 1
        if trade.net_pnl <= 0:
            self.learning_last_fault = (
                f"{trade.symbol} {trade.direction.value} finished at {trade.r_multiple:.2f}R "
                f"via {trade.exit_reason or 'unknown'}; review {', '.join(factors)}."
            )
        if not self.adaptive_learning_enabled:
            return "Learning is recorded for review; the overlay is disabled."
        if self.learning_observations < self.learning_min_samples:
            return (
                f"Learning sample {self.learning_observations}/{self.learning_min_samples} "
                "recorded; no adjustment applied yet."
            )
        return "Paper learning updated the factor reliability overlay for future entries."

    def _learning_profile(
        self, closed_trades: list[PaperTrade] | None = None
    ) -> PaperLearningProfile:
        closed_trades = closed_trades if closed_trades is not None else self._closed_trades()
        factors: list[PaperFactorPerformance] = []
        for factor, stats in sorted(
            self.learning_stats.items(),
            key=lambda item: (-int(item[1].get("samples", 0)), item[0]),
        ):
            samples = int(stats.get("samples", 0))
            wins = int(stats.get("wins", 0))
            losses = int(stats.get("losses", 0))
            factors.append(
                PaperFactorPerformance(
                    factor=factor,
                    samples=samples,
                    wins=wins,
                    losses=losses,
                    win_rate=round(wins / samples * 100, 1) if samples else 0.0,
                    average_r_multiple=round(stats.get("r_total", 0.0) / samples, 3)
                    if samples
                    else 0.0,
                )
            )
        if self.learning_observations < self.learning_min_samples:
            recommendation = (
                f"Collecting outcomes ({self.learning_observations}/{self.learning_min_samples}); "
                "the paper strategy is unchanged until the sample is meaningful."
            )
        else:
            weak = [
                item.factor
                for item in factors
                if item.samples >= self.learning_min_samples and item.win_rate < 45
            ]
            strong = [
                item.factor
                for item in factors
                if item.samples >= self.learning_min_samples and item.win_rate >= 60
            ]
            if weak:
                recommendation = (
                    "Down-weighting weak factors in paper entries: "
                    f"{', '.join(weak[:3])}."
                )
            elif strong:
                recommendation = f"Paper evidence supports these factors: {', '.join(strong[:3])}."
            else:
                recommendation = "Paper evidence is mixed; keeping the base strategy weights."
        if not self.adaptive_learning_enabled:
            future_plan = (
                "Outcomes are recorded for review, but the adaptive overlay is disabled. "
                "No factor weight will change until it is explicitly enabled in paper mode."
            )
        elif self.learning_observations < self.learning_min_samples:
            remaining = self.learning_min_samples - self.learning_observations
            future_plan = (
                f"Collect {remaining} more closed outcome{'s' if remaining != 1 else ''} before "
                "changing factor weights. Until then, the base strategy and risk limits stay fixed."
            )
        else:
            weak = [
                item.factor
                for item in factors
                if item.samples >= self.learning_min_samples and item.win_rate < 45
            ]
            strong = [
                item.factor
                for item in factors
                if item.samples >= self.learning_min_samples and item.win_rate >= 60
            ]
            if weak:
                future_plan = (
                    "Future paper entries will apply a small negative reliability adjustment to "
                    f"{', '.join(weak[:3])}; the candidate still needs the base strategy gate, "
                    "and risk limits remain unchanged."
                )
            elif strong:
                future_plan = (
                    "Future paper entries may receive a small positive reliability adjustment for "
                    f"{', '.join(strong[:3])}. This does not bypass confirmation, costs, or "
                    "risk caps."
                )
            else:
                future_plan = (
                    "Evidence is mixed, so future paper entries keep the base weights while more "
                    "closed outcomes are collected. No live rule is changed."
                )
        return PaperLearningProfile(
            enabled=self.adaptive_learning_enabled,
            mode="Paper-only adaptive overlay",
            observations=self.learning_observations,
            wins=self.learning_wins,
            losses=self.learning_losses,
            last_updated_at=self.learning_last_updated_at,
            last_fault=self.learning_last_fault,
            recommendation=recommendation,
            factor_performance=factors,
            future_plan=future_plan,
            lessons=self._learning_lessons(closed_trades),
        )

    def _daily_reports(
        self,
        closed_trades: list[PaperTrade],
        days: int = 14,
        as_of: datetime | None = None,
    ) -> list[PaperDailyReport]:
        """Build restart-safe UTC close-day reports from the persisted trade ledger."""
        today = (as_of or datetime.now(UTC)).astimezone(UTC).date()
        report_dates = [today - timedelta(days=offset) for offset in range(days)]
        reports: list[PaperDailyReport] = []
        for report_date in report_dates:
            day_trades = [
                trade
                for trade in closed_trades
                if self._trade_day(trade) == report_date
            ]
            opening_balance = self.starting_balance + sum(
                trade.net_pnl
                for trade in closed_trades
                if self._trade_day(trade) < report_date
            )
            winning_amount = sum(max(trade.net_pnl, 0.0) for trade in day_trades)
            losing_amount = sum(max(-trade.net_pnl, 0.0) for trade in day_trades)
            net_pnl = sum(trade.net_pnl for trade in day_trades)
            closed_count = len(day_trades)
            winners = sum(1 for trade in day_trades if trade.net_pnl > 0)
            losers = sum(1 for trade in day_trades if trade.net_pnl < 0)
            reports.append(
                PaperDailyReport(
                    date=report_date.isoformat(),
                    opening_balance=round(opening_balance, 2),
                    closing_balance=round(opening_balance + net_pnl, 2),
                    closed_trades=closed_count,
                    winning_trades=winners,
                    losing_trades=losers,
                    win_rate_pct=round(winners / closed_count * 100, 1)
                    if closed_count
                    else 0.0,
                    winning_amount=round(winning_amount, 2),
                    losing_amount=round(losing_amount, 2),
                    winning_pct=round(winning_amount / opening_balance * 100, 3)
                    if opening_balance > 0
                    else 0.0,
                    losing_pct=round(losing_amount / opening_balance * 100, 3)
                    if opening_balance > 0
                    else 0.0,
                    net_pnl=round(net_pnl, 2),
                    net_return_pct=round(net_pnl / opening_balance * 100, 3)
                    if opening_balance > 0
                    else 0.0,
                    fees_paid=round(
                        sum(trade.entry_fee + trade.exit_fee for trade in day_trades), 2
                    ),
                    profit_factor=round(winning_amount / losing_amount, 3)
                    if losing_amount > 0
                    else None,
                )
            )
        return reports

    def _learning_lessons(self, closed_trades: list[PaperTrade]) -> list[PaperLearningLesson]:
        lessons: list[PaperLearningLesson] = []
        for trade in sorted(
            (item for item in closed_trades if item.net_pnl <= 0),
            key=lambda item: item.closed_at or item.updated_at,
            reverse=True,
        )[:12]:
            exit_reason = trade.exit_reason or "unknown"
            if exit_reason == "stop_loss":
                fault = (
                    "The setup reached its stop before the target, so the entry confirmation "
                    "did not survive the trade."
                )
            elif exit_reason == "signal_reversal":
                fault = "The market invalidated the direction before the stop or target."
            elif exit_reason == "time_limit":
                fault = "The trade did not reach its target inside the configured holding window."
            elif exit_reason == "operator":
                fault = (
                    "The position was closed manually; this is recorded but not treated as a "
                    "strategy fault."
                )
            else:
                fault = (
                    "The virtual trade finished without a positive net result and is kept for "
                    "review."
                )
            factors = trade.factor_categories or ["manual"]
            if not self.adaptive_learning_enabled:
                future_action = (
                    "Keep the same base rule for now; the overlay is disabled, so this outcome "
                    "only informs review."
                )
            elif self.learning_observations < self.learning_min_samples:
                remaining = self.learning_min_samples - self.learning_observations
                future_action = (
                    f"Keep risk capped and collect {remaining} more "
                    f"outcome{'s' if remaining != 1 else ''} "
                    "before changing factor weights."
                )
            else:
                future_action = (
                    "Use the factor reliability overlay on similar paper entries; weak factors "
                    "receive a small negative score adjustment while the full strategy gate and "
                    "risk limits remain required."
                )
            lessons.append(
                PaperLearningLesson(
                    observed_at=trade.closed_at or trade.updated_at,
                    trade_id=trade.id,
                    symbol=trade.symbol,
                    direction=trade.direction,
                    exit_reason=exit_reason,
                    r_multiple=round(trade.r_multiple, 3),
                    factors=factors,
                    fault=fault,
                    future_action=future_action,
                )
            )
        return lessons

    @staticmethod
    def _trade_day(trade: PaperTrade) -> date:
        timestamp = trade.closed_at or trade.updated_at
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC).date()

    def _trim(self) -> None:
        open_positions = self._open_trades()
        closed_positions = sorted(
            self._closed_trades(),
            key=lambda item: item.closed_at or item.updated_at,
            reverse=True,
        )[:10000]
        self.trades = open_positions + closed_positions
        self.decisions = self.decisions[-10000:]
        self.equity_curve = self.equity_curve[-20000:]

    def _save(self) -> None:
        self.last_saved_at = datetime.now(UTC)
        payload = {
            "version": 2,
            "starting_balance": self.starting_balance,
            "enabled": self.enabled,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "max_open_positions": self.max_open_positions,
            "minimum_opportunity_score": self.minimum_opportunity_score,
            "timeframe": self.timeframe,
            "cycle_count": self.cycle_count,
            "last_cycle_at": self._datetime_text(self.last_cycle_at),
            "last_scan_at": self._datetime_text(self.last_scan_at),
            "last_error": self.last_error,
            "market_source": self.market_source,
            "source_account_id": self.source_account_id,
            "scanned_symbols": self.scanned_symbols,
            "eligible_candidates": self.eligible_candidates,
            "opened_last_cycle": self.opened_last_cycle,
            "closed_last_cycle": self.closed_last_cycle,
            "last_saved_at": self._datetime_text(self.last_saved_at),
            "learning": {
                "enabled": self.adaptive_learning_enabled,
                "observations": self.learning_observations,
                "wins": self.learning_wins,
                "losses": self.learning_losses,
                "last_updated_at": self._datetime_text(self.learning_last_updated_at),
                "last_fault": self.learning_last_fault,
                "factor_stats": self.learning_stats,
            },
            "trades": [self._serialize(item) for item in self.trades],
            "decisions": [self._serialize(item) for item in self.decisions],
            "equity_curve": [self._serialize(item) for item in self.equity_curve],
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(f"{self.state_file.suffix}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            if self.state_file.is_file():
                with suppress(OSError):
                    shutil.copy2(self.state_file, self.backup_file)
            temporary.replace(self.state_file)
            self.persistence_status = "saved"
        except OSError:
            self.persistence_status = "error"
            raise

    def _load(self) -> None:
        source_file: Path | None = None
        has_state_file = False
        for candidate in (self.state_file, self.backup_file):
            if not candidate.is_file():
                continue
            has_state_file = True
            try:
                json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            source_file = candidate
            break
        if source_file is None:
            if has_state_file:
                self.last_error = (
                    "The virtual portfolio state is damaged and no recovery copy is valid."
                )
                self.persistence_status = "error"
            return
        try:
            payload = json.loads(source_file.read_text(encoding="utf-8"))
            self.starting_balance = float(payload.get("starting_balance", self.starting_balance))
            self.enabled = bool(payload.get("enabled", self.enabled))
            self.risk_per_trade_pct = float(
                payload.get("risk_per_trade_pct", self.risk_per_trade_pct)
            )
            self.max_open_positions = int(
                payload.get("max_open_positions", self.max_open_positions)
            )
            self.minimum_opportunity_score = float(
                payload.get("minimum_opportunity_score", self.minimum_opportunity_score)
            )
            self.timeframe = str(payload.get("timeframe", self.timeframe))
            self.cycle_count = int(payload.get("cycle_count", 0))
            self.last_cycle_at = self._parse_datetime(payload.get("last_cycle_at"))
            self.last_scan_at = self._parse_datetime(payload.get("last_scan_at"))
            self.last_error = str(payload.get("last_error", ""))
            self.market_source = str(payload.get("market_source", "waiting"))
            self.source_account_id = str(payload.get("source_account_id", ""))
            self.scanned_symbols = int(payload.get("scanned_symbols", 0))
            self.eligible_candidates = int(payload.get("eligible_candidates", 0))
            self.opened_last_cycle = int(payload.get("opened_last_cycle", 0))
            self.closed_last_cycle = int(payload.get("closed_last_cycle", 0))
            self.last_saved_at = self._parse_datetime(payload.get("last_saved_at"))
            self.trades = [self._trade_from_dict(item) for item in payload.get("trades", [])]
            self.decisions = [
                self._decision_from_dict(item) for item in payload.get("decisions", [])
            ]
            self.equity_curve = [
                self._equity_from_dict(item) for item in payload.get("equity_curve", [])
            ]
            learning = payload.get("learning", {})
            if isinstance(learning, dict):
                self.learning_observations = int(learning.get("observations", 0))
                self.learning_wins = int(learning.get("wins", 0))
                self.learning_losses = int(learning.get("losses", 0))
                self.learning_last_updated_at = self._parse_datetime(
                    learning.get("last_updated_at")
                )
                self.learning_last_fault = str(learning.get("last_fault", ""))
                raw_stats = learning.get("factor_stats", {})
                if isinstance(raw_stats, dict):
                    self.learning_stats = {
                        str(factor): {
                            "samples": float(stats.get("samples", 0)),
                            "wins": float(stats.get("wins", 0)),
                            "losses": float(stats.get("losses", 0)),
                            "r_total": float(stats.get("r_total", 0)),
                        }
                        for factor, stats in raw_stats.items()
                        if isinstance(stats, dict)
                    }
            if not self.learning_observations and self._closed_trades():
                self._rebuild_learning_from_trades()
            self.persistence_status = "recovered" if source_file == self.backup_file else "saved"
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            self.last_error = "The virtual portfolio state could not be loaded; using a new ledger."
            self.persistence_status = "error"

    def _rebuild_learning_from_trades(self) -> None:
        self.learning_observations = 0
        self.learning_wins = 0
        self.learning_losses = 0
        self.learning_stats = {}
        for trade in sorted(
            self._closed_trades(), key=lambda item: item.closed_at or item.updated_at
        ):
            self._record_learning_outcome(trade)

    @staticmethod
    def _resolve_state_file(state_file: str) -> Path:
        configured = Path(state_file)
        if configured.is_absolute():
            return configured
        # Resolve relative paths from the API service directory, not the caller's cwd.
        api_directory = Path(__file__).resolve().parents[2]
        return (api_directory / configured).resolve()

    @staticmethod
    def _serialize(item: Any) -> dict[str, Any]:
        payload = asdict(item)
        for key, value in list(payload.items()):
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
            elif isinstance(value, Direction):
                payload[key] = value.value
        return payload

    @staticmethod
    def _trade_from_dict(payload: dict[str, Any]) -> PaperTrade:
        return PaperTrade(
            **{
                **payload,
                "direction": Direction(payload["direction"]),
                "opened_at": PaperTradingService._parse_datetime(payload["opened_at"]),
                "updated_at": PaperTradingService._parse_datetime(payload["updated_at"]),
                "closed_at": PaperTradingService._parse_datetime(payload.get("closed_at")),
            }
        )

    @staticmethod
    def _decision_from_dict(payload: dict[str, Any]) -> PaperDecision:
        direction = payload.get("signal_direction")
        return PaperDecision(
            **{
                **payload,
                "created_at": PaperTradingService._parse_datetime(payload["created_at"]),
                "signal_direction": Direction(direction) if direction else None,
            }
        )

    @staticmethod
    def _equity_from_dict(payload: dict[str, Any]) -> PaperEquityPoint:
        return PaperEquityPoint(
            **{
                **payload,
                "timestamp": PaperTradingService._parse_datetime(payload["timestamp"]),
            }
        )

    @staticmethod
    def _datetime_text(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
