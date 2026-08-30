# Trader AI Workstation

TradingView-inspired AI trading workstation for market scanning, explainable signals, paper trading, backtesting, and guarded broker integration.

This project is **not** a profit guarantee and does not ship with live trading enabled. It defaults to paper trading and requires explicit environment configuration plus operator confirmation before any live broker adapter can place orders.

## What is included

- Responsive workstation UI for Windows 11 desktops, multi-monitor layouts, and Android phones.
- Splittable chart grid with priority symbols: `XAUUSD`, `XAGUSD`, `BTCUSD`, `US100.std`, `US30.std`, `WTI.m`, and `BRENT.m`.
- Signal-only and auto-trade modes, with auto-trade locked behind server-side live-trading guardrails.
- Explainable Regime-Aligned Pullback signal engine with EMA slope, ADX/DI strength, RSI(14)
  mid-zone momentum, pullback/breakout structure, volume, volatility, and event/news rationale.
- Paper broker as the default execution engine.
- Persistent virtual trading ledger that opens, marks, closes, and reports every eligible paper
  position with entry, exit, fees, risk, R-multiple, MFE/MAE, equity, decision history, and
  paper-only learning from closed-trade outcomes.
- Separate persistent Extreme Virtual Trading ledger for confirmed RSI(1) 85/15 plus rejection,
  RSI(3/7), momentum, MACD histogram, and EMA agreement, including signal-time price, modeled
  fill, live virtual P/L, exit result, and learning.
- MT5/JustMarkets integration boundary with a disabled-by-default adapter contract.
- Persistent multi-account profiles with masked logins and an in-workstation account selector.
- Windows MT5 read-only bridge for verified account metrics, broker quotes, and open positions.
- Verified MT5 candles for charts, explainable signals, and backtests with visible source labels.
- Analysis-first news workspace with global and per-symbol impact, scenarios, timing, confidence,
  source freshness, and explicit uncertainty.
- Read-only MT5 economic-calendar exporter for scheduled USD macro events.
- Whole-broker market scan across every tradeable MT5 instrument, ranked by signal quality,
  spread cost, quote freshness, and current market availability.
- Separate 85/15 extreme monitor combining RSI(1), MACD(5,6,1), and moving-average context, with
  threshold-entry alerts, cooldowns, browser sound, and optional voice announcements.
- MT5 chart indicators for the M1 10/90 reversal setup and reusable multi-timeframe EMA/RSI/MACD/
  ADX trend confirmation on M5 through D1.
- Standalone research-based MT5 Strategy Tester EA using breakout, trend, momentum, ATR risk,
  walk-forward-friendly optimization scoring, and live-order locks.
- Per-chart indicator workspace with selectable overlays, oscillator readings, configurable
  parameters, presets, saved layouts, and an explainable AI-assisted bias summary.
- Searchable left market drawer for adding, removing, and drag-ordering charts, plus direct chart
  move handles, with local persistence.
- Chart zoom controls and candle inspection with exact start/end time, OHLC, and volume.
- Resizable chart tiles with mouse, touch, and keyboard controls; each chart height is saved
  locally per device.
- Per-chart advanced indicator stack with RSI(1) 85/15 zones, MACD(5,6,1), EMA 12/36, ATR(15),
  and 24-candle structure context.
- Visible active strategy definition, factor weights, entry threshold, stop model, and target model.
- Backtesting service for strategy validation before deployment.
- Continuous scanner service shape for background monitoring.
- Alert hooks for browser audio, speech synthesis, webhooks, and future mobile push.
- Docker Compose deployment for API, web, Redis, Postgres, Prometheus, and Grafana.
- CI for Python unit tests and frontend type/lint/build checks.

## Quick Start

### Local API

```bash
cd services/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Local Web App

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:5173`. The UI reads the API from `VITE_API_URL`, defaulting to `http://localhost:8000`.

For multiple MT5 accounts, copy `config/mt5-accounts.example.json` to
`data/mt5-accounts.json` and add the non-secret account profiles. The `data` directory is ignored
by Git. Sign into the selected account in MT5; do not store trading passwords in the profile file.
The API verifies that MT5 is signed into the selected profile before exposing account values.

The first whole-market scan can take around 30 seconds because it loads broker candles for every
tradeable instrument. Results are cached for five minutes; selected charts load first and remain
usable while the background scan runs.

### Docker

```bash
cp .env.example .env
docker compose up --build
```

Services:

- Web UI: `http://localhost:5173`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## Live Trading Safety

Live trading is blocked unless all of these are true:

- `TRADING_MODE=live`
- `LIVE_TRADING_ENABLED=true`
- `LIVE_TRADING_ACKNOWLEDGEMENT` is set to the exact configured acknowledgement phrase
- A real broker adapter is selected and configured
- The risk engine approves the order

The shipped default is:

```env
TRADING_MODE=paper
LIVE_TRADING_ENABLED=false
BROKER_ADAPTER=paper
```

## Documentation

- [Architecture](docs/architecture.md)
- [Deployment Guide](docs/deployment.md)
- [Risk Guardrails](docs/risk.md)
- [MT5 and JustMarkets Integration](docs/mt5-justmarkets.md)
- [News Analysis](docs/news-analysis.md)
- [Whole-Market Scanner](docs/market-scanner.md)
- [Virtual Paper Trading](docs/paper-trading.md)
- [Regime-Aligned Strategy](docs/regime-aligned-strategy.md)
- [85/15 Extreme Scanner](docs/extreme-scanner.md)
- [Research Strategy Tester EA](docs/research-trend-strategy.md)
- [Chart Indicators and AI Reading](docs/chart-indicators.md)
- [Operations Runbook](docs/operations.md)

## Repository Layout

```text
apps/web             React workstation UI
services/api         Python API, scanner, strategy, risk, broker boundaries
docs                 Setup, safety, and operations documentation
.github/workflows    CI
```

## Important Notice

Trading leveraged products, metals, crypto, indices, and oil can cause rapid losses. Treat every signal as decision support, test strategies with paper trading and backtests, and use small risk limits. The system is designed to explain and constrain decisions, not to promise returns.
