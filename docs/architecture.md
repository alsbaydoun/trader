# Architecture

## Goals

Trader is designed as an operator-controlled workstation. It supports market scanning, explainable signals, paper execution, backtesting, and broker integration points. The first version intentionally blocks live trading by default.

## Components

- **Web workstation**: React/Vite UI for Windows, Android, and large multi-monitor setups. Charts render with canvas so panels can resize and pop out into separate browser windows.
- **API service**: FastAPI application exposing status, candles, scans, signals, backtests, positions, order placement, and metrics.
- **Scanner worker**: Continuous loop that scans configured symbols and can later publish to Redis, websockets, email, mobile push, or voice channels.
- **Strategy layer**: Deterministic signal engine combining EMA trend, momentum, MACD, RSI(1),
  structure, ATR volatility, and explicit reason objects. The web chart renders the same indicator
  context beneath each chart.
- **News analysis layer**: Converts verified economic-calendar inputs into global and per-symbol
  scenarios, transmission chains, timing windows, confidence, and invalidation conditions. Missing
  headline coverage is exposed rather than silently replaced with generated content.
- **Market opportunity scanner**: Enumerates the active MT5 account's tradeable catalog, scans each
  instrument, and ranks current setups. It penalizes spread cost, stale quotes, inactive sessions,
  and weak directional conviction.
- **Extreme scanner**: Independently reads the whole MT5 catalog and computes the requested RSI(1),
  MACD(5,6,1), and moving-average context. It ranks a composite 0-100 score, detects entry into
  the 85/15 zones, and retains alert history without creating orders.
- **Paper trading service**: Persists a virtual ledger, processes market cycles, applies simulated
  slippage and commission, closes positions on stop, target, reversal, time limit, or operator
  action, exposes detailed equity and decision history, and records a conservative paper-only
  factor reliability overlay from closed outcomes. Saves are atomic and keep a recovery copy.
- **Extreme paper trading service**: Converts confirmed 85/15 alerts into a second persistent
  paper-only ledger. It shares the execution lifecycle and cost model but keeps its balance,
  positions, results, and learning history separate from broad-market paper trading.
- **Risk engine**: Server-side order gate enforcing stop losses, max risk per trade, max daily loss, max open positions, and symbol exposure.
- **Broker adapters**: Paper broker is enabled by default. MT5/JustMarkets is represented as an adapter boundary and remains locked until explicit live settings are supplied.
- **Observability**: Prometheus metrics plus Docker Compose hooks for Grafana.

## Data Flow

1. UI requests `/scan`.
2. API loads market candles from the configured market data provider.
3. Signal engine produces directional confidence and explainable reasons.
4. News service attaches verified event analysis and source state.
5. The broker-wide scanner independently ranks all available instruments, even when they are not
   open as charts.
6. UI displays charts, reasons, strategy definition, news analysis, market ranking, and alert hooks.
7. The paper loop can process eligible signals into the broad virtual ledger, while the extreme loop
   can process confirmed 85/15 signals into its separate virtual ledger; no MT5 order function is called.
8. If auto mode is selected for a live integration, any order request still passes through the API risk engine and broker safety locks.

## Extensibility

Add new symbols in `services/api/app/domain/symbols.py` or through a future database-backed symbol registry. Add paid feeds by replacing `MarketDataService` with a provider implementation that preserves the `candles(symbol, timeframe, limit)` contract.

Recommended paid data/news integrations to consider later:

- TradingView-compatible charting/data vendor or broker market data feed.
- Economic calendar feed with central bank, CPI, jobs, inventory, and geopolitical alerts.
- Low-latency crypto market feed for BTCUSD.
- Broker-side symbol metadata from the actual MT5 terminal before live execution.

No external vendor is hard-coded because credentials, terms, latency, and symbol naming must be selected account by account.
