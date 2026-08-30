from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ReasonDTO(APIModel):
    category: str
    message: str
    impact: Literal["bullish", "bearish", "neutral", "risk"]
    weight: float


class SignalDTO(APIModel):
    symbol: str
    timeframe: str
    direction: Literal["buy", "sell", "hold"]
    confidence: float
    entry: float
    stop_loss: float | None
    take_profit: float | None
    reasons: list[ReasonDTO]
    source: Literal["demo", "mt5"]
    created_at: datetime


class CandleDTO(APIModel):
    symbol: str
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: Literal["demo", "mt5"]


class OrderRequestDTO(APIModel):
    symbol: str
    direction: Literal["buy", "sell", "hold"]
    volume: float = Field(gt=0)
    entry: float = Field(gt=0)
    stop_loss: float | None = None
    take_profit: float | None = None
    mode: Literal["signal_only", "auto_trade"] = "signal_only"


class RiskDecisionDTO(APIModel):
    approved: bool
    reason: str
    max_volume: float


class PositionDTO(APIModel):
    id: str
    symbol: str
    direction: Literal["buy", "sell", "hold"]
    volume: float
    entry: float
    stop_loss: float | None
    take_profit: float | None
    opened_at: datetime


class PaperTradeDTO(APIModel):
    id: str
    symbol: str
    direction: Literal["buy", "sell"]
    timeframe: str
    status: Literal["open", "closed"]
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
    closed_at: datetime | None
    exit_price: float | None
    exit_reason: Literal[
        "stop_loss",
        "take_profit",
        "signal_reversal",
        "time_limit",
        "operator",
    ] | None
    max_favorable_excursion: float
    max_adverse_excursion: float
    factor_categories: list[str]
    learning_adjustment: float
    learned_score: float
    signal_at: datetime | None
    signal_price: float | None
    signal_level: str | None
    signal_recommendation: str | None


class PaperDecisionDTO(APIModel):
    id: str
    cycle_id: str
    created_at: datetime
    action: Literal["cycle", "opened", "closed", "error", "control"]
    outcome: str
    reason: str
    symbol: str | None
    trade_id: str | None
    signal_direction: Literal["buy", "sell", "hold"] | None
    opportunity_score: float | None


class PaperEquityPointDTO(APIModel):
    timestamp: datetime
    equity: float
    balance: float
    unrealized_pnl: float


class PaperFactorPerformanceDTO(APIModel):
    factor: str
    samples: int
    wins: int
    losses: int
    win_rate: float
    average_r_multiple: float


class PaperDailyReportDTO(APIModel):
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


class PaperLearningLessonDTO(APIModel):
    observed_at: datetime
    trade_id: str
    symbol: str
    direction: Literal["buy", "sell"]
    exit_reason: str
    r_multiple: float
    factors: list[str]
    fault: str
    future_action: str


class PaperLearningProfileDTO(APIModel):
    enabled: bool
    mode: str
    observations: int
    wins: int
    losses: int
    last_updated_at: datetime | None
    last_fault: str
    recommendation: str
    factor_performance: list[PaperFactorPerformanceDTO]
    future_plan: str
    lessons: list[PaperLearningLessonDTO]


class PaperPersistenceStatusDTO(APIModel):
    storage: str
    state_version: int
    status: str
    last_saved_at: datetime | None
    backup_available: bool


class PaperEngineStatusDTO(APIModel):
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


class PaperMetricsDTO(APIModel):
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


class PaperPortfolioDTO(APIModel):
    engine: PaperEngineStatusDTO
    metrics: PaperMetricsDTO
    open_positions: list[PaperTradeDTO]
    closed_trades: list[PaperTradeDTO]
    decisions: list[PaperDecisionDTO]
    equity_curve: list[PaperEquityPointDTO]
    learning: PaperLearningProfileDTO
    daily_reports: list[PaperDailyReportDTO]
    persistence: PaperPersistenceStatusDTO
    disclaimer: str


class PaperControlRequestDTO(APIModel):
    enabled: bool | None = None
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d"] | None = None
    minimum_opportunity_score: float | None = Field(default=None, ge=0, le=100)
    max_open_positions: int | None = Field(default=None, ge=1, le=200)


class PaperResetRequestDTO(APIModel):
    confirmation: str


class BacktestDTO(APIModel):
    symbol: str
    timeframe: str
    trades: int
    win_rate: float
    net_return_pct: float
    max_drawdown_pct: float
    source: Literal["demo", "mt5"]


class ExtremeBacktestTradeDTO(APIModel):
    direction: Literal["buy", "sell"]
    signal_at: datetime
    entry_at: datetime
    exit_at: datetime
    signal_price: float
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    outcome: Literal["win", "loss", "flat"]
    exit_reason: Literal["stop_loss", "take_profit", "time_limit", "data_end"]
    return_pct: float
    r_multiple: float
    score: int
    reasons: list[str]


class ExtremeBacktestDTO(APIModel):
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
    trades_detail: list[ExtremeBacktestTradeDTO]


class StrategyDTO(APIModel):
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


class MarketImpactDTO(APIModel):
    symbol: str
    direction: Literal["bullish", "bearish", "mixed", "neutral"]
    confidence: float
    horizon: str
    thesis: str
    causal_chain: list[str]
    bullish_trigger: str
    bearish_trigger: str
    invalidation: str


class MarketEventDTO(APIModel):
    id: str
    title: str
    category: str
    scope: Literal["global", "symbol"]
    symbols: list[str]
    severity: Literal["low", "medium", "high"]
    source: str
    source_url: str | None
    published_at: datetime
    event_time: datetime
    analysis: str
    why_it_matters: list[str]
    risk_window: str
    actual: float | None
    forecast: float | None
    previous: float | None
    impacts: list[MarketImpactDTO]


class NewsStatusDTO(APIModel):
    provider: str
    state: Literal["live", "stale", "config_required", "error"]
    message: str
    calendar_connected: bool
    headlines_connected: bool
    updated_at: datetime


class NewsFeedDTO(APIModel):
    status: NewsStatusDTO
    events: list[MarketEventDTO]


class ScanDTO(APIModel):
    signals: list[SignalDTO]
    events: list[MarketEventDTO]
    news_status: NewsStatusDTO


class BrokerAccountDTO(APIModel):
    id: str
    provider: str
    server: str
    account_type: str
    login_masked: str
    active: bool
    profile_configured: bool
    terminal_configured: bool
    connection_verified: bool
    connection_ready: bool


class AccountListDTO(APIModel):
    active_account_id: str | None
    accounts: list[BrokerAccountDTO]


class ActiveAccountRequestDTO(APIModel):
    account_id: str = Field(min_length=3)


class MT5ConnectionDTO(APIModel):
    status: str
    message: str
    read_only: bool
    package_available: bool
    initialized: bool
    terminal_connected: bool
    account_matches: bool
    server_matches: bool
    connection_verified: bool
    selected_login_masked: str
    terminal_login_masked: str
    terminal_server: str
    package_version: str
    terminal_version: str
    company: str
    currency: str
    leverage: int
    balance: float | None
    equity: float | None
    profit: float | None
    margin: float | None
    margin_free: float | None
    margin_level: float | None
    trade_allowed: bool
    expert_orders_allowed: bool
    symbols_count: int
    positions_count: int
    updated_at: datetime


class MT5QuoteDTO(APIModel):
    requested_symbol: str
    symbol: str
    bid: float
    ask: float
    spread: float
    digits: int
    visible: bool
    trade_mode: int
    updated_at: datetime


class MT5PositionDTO(APIModel):
    ticket: str
    symbol: str
    direction: Literal["buy", "sell"]
    volume: float
    price_open: float
    price_current: float
    stop_loss: float | None
    take_profit: float | None
    profit: float
    opened_at: datetime


class MarketSymbolDTO(APIModel):
    symbol: str
    description: str
    category: str
    currency_base: str
    currency_profit: str
    digits: int
    bid: float
    ask: float
    spread_points: float
    visible: bool
    trade_mode: int
    last_tick_at: datetime | None
    source: Literal["mt5", "configured"]


class MarketOpportunityDTO(APIModel):
    rank: int
    symbol: str
    description: str
    category: str
    direction: Literal["buy", "sell", "hold"]
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
    reasons: list[ReasonDTO]


class MarketScanDTO(APIModel):
    source: str
    timeframe: str
    available_symbols: int
    scanned_symbols: int
    generated_at: datetime
    disclaimer: str
    opportunities: list[MarketOpportunityDTO]


class ExtremeReadingDTO(APIModel):
    symbol: str
    price: float
    score: float
    level: Literal["upper_85", "lower_15", "neutral"]
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


class ExtremeAlertDTO(APIModel):
    id: str
    symbol: str
    level: Literal["upper_85", "lower_15"]
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


class ExtremeScanDTO(APIModel):
    source: str
    timeframe: str
    available_symbols: int
    scanned_symbols: int
    generated_at: datetime
    upper_level: float
    lower_level: float
    readings: list[ExtremeReadingDTO]
    alerts: list[ExtremeAlertDTO]
    recent_alerts: list[ExtremeAlertDTO]
    disclaimer: str


class StrategyLabMemberDTO(APIModel):
    id: str
    name: str
    summary: str
    upper_level: float
    lower_level: float
    target_r: float
    stop_atr: float
    max_minutes: int
    criteria: list[str]
    candidates_last_cycle: int
    portfolio: PaperPortfolioDTO


class StrategyLabDTO(APIModel):
    source: str
    timeframe: str
    generated_at: datetime
    leader_strategy_id: str | None
    strategies: list[StrategyLabMemberDTO]
    main_lessons: list[str]
    disclaimer: str


class StatusDTO(APIModel):
    trading_mode: str
    broker_adapter: str
    live_trading_enabled: bool
    live_trading_unlocked: bool
    default_symbols: list[str]
    guardrails: dict[str, float | int]
    broker_account: BrokerAccountDTO | None
    mt5: MT5ConnectionDTO
