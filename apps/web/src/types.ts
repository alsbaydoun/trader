export type Direction = "buy" | "sell" | "hold";
export type TradeMode = "signal_only" | "auto_trade";

export interface Candle {
  symbol: string;
  timeframe: string;
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  source: "demo" | "mt5";
}

export interface SignalReason {
  category: string;
  message: string;
  impact: "bullish" | "bearish" | "neutral" | "risk";
  weight: number;
}

export interface Signal {
  symbol: string;
  timeframe: string;
  direction: Direction;
  confidence: number;
  entry: number;
  stop_loss: number | null;
  take_profit: number | null;
  reasons: SignalReason[];
  source: "demo" | "mt5";
  created_at: string;
}

export interface MarketEvent {
  id: string;
  title: string;
  category: string;
  scope: "global" | "symbol";
  symbols: string[];
  severity: "low" | "medium" | "high";
  source: string;
  source_url: string | null;
  published_at: string;
  event_time: string;
  analysis: string;
  why_it_matters: string[];
  risk_window: string;
  actual: number | null;
  forecast: number | null;
  previous: number | null;
  impacts: MarketImpact[];
}

export interface MarketImpact {
  symbol: string;
  direction: "bullish" | "bearish" | "mixed" | "neutral";
  confidence: number;
  horizon: string;
  thesis: string;
  causal_chain: string[];
  bullish_trigger: string;
  bearish_trigger: string;
  invalidation: string;
}

export interface NewsStatus {
  provider: string;
  state: "live" | "stale" | "config_required" | "error";
  message: string;
  calendar_connected: boolean;
  headlines_connected: boolean;
  updated_at: string;
}

export interface NewsFeed {
  status: NewsStatus;
  events: MarketEvent[];
}

export interface ScanResponse {
  signals: Signal[];
  events: MarketEvent[];
  news_status: NewsStatus;
}

export interface Status {
  trading_mode: string;
  broker_adapter: string;
  live_trading_enabled: boolean;
  live_trading_unlocked: boolean;
  default_symbols: string[];
  guardrails: Record<string, number>;
  broker_account: BrokerAccount | null;
  mt5: MT5Connection;
}

export interface BrokerAccount {
  id: string;
  provider: string;
  server: string;
  account_type: string;
  login_masked: string;
  active: boolean;
  profile_configured: boolean;
  terminal_configured: boolean;
  connection_verified: boolean;
  connection_ready: boolean;
}

export interface AccountList {
  active_account_id: string | null;
  accounts: BrokerAccount[];
}

export interface MT5Connection {
  status: string;
  message: string;
  read_only: boolean;
  package_available: boolean;
  initialized: boolean;
  terminal_connected: boolean;
  account_matches: boolean;
  server_matches: boolean;
  connection_verified: boolean;
  selected_login_masked: string;
  terminal_login_masked: string;
  terminal_server: string;
  package_version: string;
  terminal_version: string;
  company: string;
  currency: string;
  leverage: number;
  balance: number | null;
  equity: number | null;
  profit: number | null;
  margin: number | null;
  margin_free: number | null;
  margin_level: number | null;
  trade_allowed: boolean;
  expert_orders_allowed: boolean;
  symbols_count: number;
  positions_count: number;
  updated_at: string;
}

export interface MT5Quote {
  requested_symbol: string;
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  digits: number;
  visible: boolean;
  trade_mode: number;
  last_tick_at: string | null;
  updated_at: string;
}

export interface MT5Position {
  ticket: string;
  symbol: string;
  direction: "buy" | "sell";
  volume: number;
  price_open: number;
  price_current: number;
  stop_loss: number | null;
  take_profit: number | null;
  profit: number;
  opened_at: string;
}

export interface Backtest {
  symbol: string;
  timeframe: string;
  trades: number;
  win_rate: number;
  net_return_pct: number;
  max_drawdown_pct: number;
  source: "demo" | "mt5";
}

export interface ExtremeBacktestTrade {
  direction: "buy" | "sell";
  signal_at: string;
  entry_at: string;
  exit_at: string;
  signal_price: number;
  entry_price: number;
  exit_price: number;
  stop_loss: number;
  take_profit: number;
  outcome: "win" | "loss" | "flat";
  exit_reason: "stop_loss" | "take_profit" | "time_limit" | "data_end";
  return_pct: number;
  r_multiple: number;
  score: number;
  reasons: string[];
}

export interface ExtremeBacktest {
  symbol: string;
  timeframe: string;
  source: "demo" | "mt5";
  bars_tested: number;
  signals: number;
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  net_return_pct: number;
  max_drawdown_pct: number;
  profit_factor: number | null;
  total_r: number;
  average_r_multiple: number;
  data_start: string;
  data_end: string;
  stop_atr_multiple: number;
  target_r_multiple: number;
  max_hold_bars: number;
  parameters: string[];
  assumptions: string[];
  trades_detail: ExtremeBacktestTrade[];
}

export interface MarketSymbol {
  symbol: string;
  description: string;
  category: string;
  currency_base: string;
  currency_profit: string;
  digits: number;
  bid: number;
  ask: number;
  spread_points: number;
  visible: boolean;
  trade_mode: number;
  source: "mt5" | "configured";
}

export interface MarketOpportunity {
  rank: number;
  symbol: string;
  description: string;
  category: string;
  direction: Direction;
  confidence: number;
  entry: number;
  stop_loss: number | null;
  take_profit: number | null;
  opportunity_score: number;
  estimated_move_pct: number;
  spread_pct: number;
  market_active: boolean;
  quote_age_seconds: number | null;
  recommendation: string;
  reasons: SignalReason[];
}

export interface MarketScan {
  source: string;
  timeframe: string;
  available_symbols: number;
  scanned_symbols: number;
  generated_at: string;
  disclaimer: string;
  opportunities: MarketOpportunity[];
}

export interface StrategyDefinition {
  name: string;
  version: string;
  summary: string;
  components: string[];
  minimum_candles: number;
  entry_threshold: number;
  stop_model: string;
  target_model: string;
  adaptive_learning: boolean;
  caveat: string;
}

export interface PaperTrade {
  id: string;
  symbol: string;
  direction: "buy" | "sell";
  timeframe: string;
  status: "open" | "closed";
  quantity: number;
  entry_price: number;
  current_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  risk_amount: number;
  entry_fee: number;
  exit_fee: number;
  gross_pnl: number;
  net_pnl: number;
  unrealized_pnl: number;
  return_pct: number;
  r_multiple: number;
  confidence: number;
  opportunity_score: number;
  scan_rank: number;
  reasons: string[];
  source: string;
  source_account_id: string;
  opened_at: string;
  updated_at: string;
  closed_at: string | null;
  exit_price: number | null;
  exit_reason: "stop_loss" | "take_profit" | "signal_reversal" | "time_limit" | "operator" | null;
  max_favorable_excursion: number;
  max_adverse_excursion: number;
  factor_categories: string[];
  learning_adjustment: number;
  learned_score: number;
  signal_at: string | null;
  signal_price: number | null;
  signal_level: string | null;
  signal_recommendation: string | null;
}

export interface PaperDecision {
  id: string;
  cycle_id: string;
  created_at: string;
  action: "cycle" | "opened" | "closed" | "error" | "control";
  outcome: string;
  reason: string;
  symbol: string | null;
  trade_id: string | null;
  signal_direction: Direction | null;
  opportunity_score: number | null;
}

export interface PaperEquityPoint {
  timestamp: string;
  equity: number;
  balance: number;
  unrealized_pnl: number;
}

export interface PaperFactorPerformance {
  factor: string;
  samples: number;
  wins: number;
  losses: number;
  win_rate: number;
  average_r_multiple: number;
}

export interface PaperLearningProfile {
  enabled: boolean;
  mode: string;
  observations: number;
  wins: number;
  losses: number;
  last_updated_at: string | null;
  last_fault: string;
  recommendation: string;
  factor_performance: PaperFactorPerformance[];
  future_plan: string;
  lessons: PaperLearningLesson[];
}

export interface PaperLearningLesson {
  observed_at: string;
  trade_id: string;
  symbol: string;
  direction: "buy" | "sell";
  exit_reason: string;
  r_multiple: number;
  factors: string[];
  fault: string;
  future_action: string;
}

export interface PaperDailyReport {
  date: string;
  opening_balance: number;
  closing_balance: number;
  closed_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  winning_amount: number;
  losing_amount: number;
  winning_pct: number;
  losing_pct: number;
  net_pnl: number;
  net_return_pct: number;
  fees_paid: number;
  profit_factor: number | null;
}

export interface PaperPersistenceStatus {
  storage: string;
  state_version: number;
  status: string;
  last_saved_at: string | null;
  backup_available: boolean;
}

export interface PaperEngineStatus {
  enabled: boolean;
  virtual_only: boolean;
  timeframe: string;
  minimum_opportunity_score: number;
  max_open_positions: number;
  risk_per_trade_pct: number;
  cycle_interval_seconds: number;
  cycle_count: number;
  last_cycle_at: string | null;
  last_scan_at: string | null;
  next_cycle_at: string | null;
  last_error: string;
  market_source: string;
  source_account_id: string;
  scanned_symbols: number;
  eligible_candidates: number;
  opened_last_cycle: number;
  closed_last_cycle: number;
}

export interface PaperMetrics {
  starting_balance: number;
  balance: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_return_pct: number;
  open_positions: number;
  closed_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  profit_factor: number | null;
  average_r_multiple: number;
  max_drawdown_pct: number;
  open_risk_amount: number;
  fees_paid: number;
  best_trade: number | null;
  worst_trade: number | null;
}

export interface PaperPortfolio {
  engine: PaperEngineStatus;
  metrics: PaperMetrics;
  open_positions: PaperTrade[];
  closed_trades: PaperTrade[];
  decisions: PaperDecision[];
  equity_curve: PaperEquityPoint[];
  learning: PaperLearningProfile;
  daily_reports: PaperDailyReport[];
  persistence: PaperPersistenceStatus;
  disclaimer: string;
}

export interface PaperControl {
  enabled?: boolean;
  timeframe?: "1m" | "5m" | "15m" | "1h" | "4h" | "1d";
  minimum_opportunity_score?: number;
  max_open_positions?: number;
}

export type ExtremeLevel = "upper_85" | "lower_15" | "neutral";

export interface ExtremeReading {
  symbol: string;
  price: number;
  score: number;
  level: ExtremeLevel;
  rsi1: number;
  macd: number;
  macd_signal: number;
  macd_histogram: number;
  ema_fast: number;
  ema_slow: number;
  recommendation: string;
  reasons: string[];
  source: string;
  detected_at: string;
  rsi3: number;
  rsi7: number;
  momentum_pct: number;
  candle_direction: string;
  atr_pct: number;
  reversal_confirmed: boolean;
}

export interface ExtremeAlert {
  id: string;
  symbol: string;
  level: "upper_85" | "lower_15";
  score: number;
  rsi1: number;
  macd: number;
  macd_signal: number;
  ema_fast: number;
  ema_slow: number;
  recommendation: string;
  reasons: string[];
  triggered_at: string;
  source: string;
  rsi3: number;
  rsi7: number;
  momentum_pct: number;
  candle_direction: string;
  atr_pct: number;
  reversal_confirmed: boolean;
}

export interface ExtremeScan {
  source: string;
  timeframe: string;
  available_symbols: number;
  scanned_symbols: number;
  generated_at: string;
  upper_level: number;
  lower_level: number;
  readings: ExtremeReading[];
  alerts: ExtremeAlert[];
  recent_alerts: ExtremeAlert[];
  disclaimer: string;
}

export interface StrategyLabMember {
  id: string;
  name: string;
  summary: string;
  upper_level: number;
  lower_level: number;
  target_r: number;
  stop_atr: number;
  max_minutes: number;
  criteria: string[];
  candidates_last_cycle: number;
  portfolio: PaperPortfolio;
}

export interface StrategyLabSnapshot {
  source: string;
  timeframe: string;
  generated_at: string;
  leader_strategy_id: string | null;
  strategies: StrategyLabMember[];
  main_lessons: string[];
  disclaimer: string;
}
