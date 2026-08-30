# MT5 and JustMarkets Integration

The repository includes a working read-only MT5 bridge and an execution boundary that deliberately
does not place real MT5 orders yet.

## Intended Deployment

For JustMarkets accounts through MetaTrader 5:

1. Install MT5 on a dedicated Windows 11 VPS or always-on Windows machine.
2. Log into the JustMarkets Pro account in the MT5 terminal.
3. Verify exact broker symbol names, including suffixes such as `.std` or `.m`.
4. Install the Python `MetaTrader5` package in the API runtime on the same Windows host. It is
   included automatically by `requirements.txt` on Windows.
5. Set MT5 environment variables in `.env`.
6. Keep `TRADING_MODE=paper` until account, symbol, volume, and stop behavior have been tested.

Copy `config/mt5-accounts.example.json` to the ignored `data/mt5-accounts.json` file and add each
account profile there. The web interface can switch the active account and persists that choice.
The API reports only masked logins to the browser; full logins remain in the ignored local file.

Passwords are not stored in the account profile. Sign in through the MT5 terminal; the API uses
the terminal's saved session and verifies the selected login and server before exposing account
data. Selecting another account clears verification and never unlocks live execution by itself.

Use each profile's `symbol_map` when the broker adds suffixes. For example, a workstation symbol
such as `XAUUSD` can map to the JustMarkets instrument `XAUUSD.m`.

## Read-only Bridge

With `MT5_READ_ONLY_ENABLED=true`, the bridge may call only terminal/account information, symbol,
tick, candle, and position APIs. The web workstation displays connection state, masked login
comparison, balance, equity, margin, live quotes, and position count after the selected profile
matches MT5.

Verified MT5 candles feed the charts, explainable signal engine, and backtest service. Every chart,
signal, and backtest displays an `MT5 data` or `Demo data` source badge. If the bridge is unavailable,
the account does not match, or fewer than 40 broker candles are returned, the endpoint falls back
to deterministic demo candles and labels them accordingly.

The current bridge does not call `order_send`. Live trading also remains locked while read-only
mode is enabled, even if the other live-trading acknowledgement settings are present.

## Economic Calendar Bridge

The official MT5 Python package does not expose the terminal News tab or the MQL5 economic-calendar
functions. `integrations/mt5/TraderCalendarBridge.mq5` is therefore a separate, read-only Expert
Advisor that exports scheduled USD calendar events to the MT5 common-files directory every minute.
It contains no order placement code.

The repository contains the source file only; it is not automatically installed in every MT5 data
profile. In the active MT5 terminal, use `File -> Open Data Folder`, open `MQL5/Experts`, and copy
`TraderCalendarBridge.mq5` there. You may create an optional `TraderAI` subfolder, but `TraderAI`
is a folder name, not the Expert Advisor name. Open the file in MetaEditor, press `F7` to compile,
return to MT5, right-click `Navigator -> Expert Advisors`, choose `Refresh`, and attach the
Expert Advisor named **TraderCalendarBridge** to one chart. If it does not appear, confirm that
MetaEditor opened the same data folder as the running terminal and refresh the Navigator again.

The API automatically reads:

```text
%APPDATA%\MetaQuotes\Terminal\Common\Files\TraderAI-calendar.csv
```

The workstation then displays `Live calendar`. If the export is older than ten minutes, it displays
`Stale`. This bridge covers scheduled economic events only. Broker News-tab articles and
unscheduled headlines still require a separately licensed news provider.

## M1 Paper Scalp Indicator

`integrations/mt5/TraderAI_M1_ExtremeScalp.mq5` is a chart indicator for the M1 timeframe. It uses
the 10/90 RSI extreme as a setup zone and waits for a rejection candle, RSI3/RSI7 direction,
MACD histogram movement, and an optional higher-timeframe bias before drawing a signal. It also
shows fast/slow EMAs, the current score, an explainable waiting reason, and paper-only entry,
stop, and target estimates. A signal is never a guarantee of a reversal.

Copy the file into `MQL5/Indicators/TraderAI`, compile it in MetaEditor, refresh Navigator, and
attach **TraderAI_M1_ExtremeScalp** to an M1 chart. Its default inputs keep terminal alerts and
the common-file paper signal log enabled while leaving real order placement impossible. The log
is written to `FILE_COMMON` as `TraderAI-mt5-paper-signals.csv` when a new confirmed signal occurs.
The indicator is intentionally separate from `TraderCalendarBridge`; attach both to a chart when
you want calendar export and chart signals at the same time.

## Multi-timeframe Trend Indicator

`integrations/mt5/TraderAI_MultiTimeframeTrend.mq5` is a second, reusable chart indicator for
trend-continuation setups on M5, M15, M30, H1, H4, and D1 charts. Attach it to the chart whose
timeframe you want to analyze; its default `AnalysisTimeframe=PERIOD_CURRENT` follows that chart.
You can instead choose a fixed analysis timeframe in the Inputs tab when you want several charts
to share the same signal timeframe.

The default confirmation stack combines EMA 20/50 direction, RSI(14), MACD(12/26/9), ADX(14),
and a completed H4 directional bias. It draws historical BUY and SELL arrows only after a candle
closes, shows the current PAPER ONLY status and the reason for WAIT, and estimates an ATR-based
stop and target for review. These are confirmation rules, not a promise of profitable results;
WAIT is expected when the filters disagree or market conditions are weak.

Copy the file into `MQL5/Indicators/TraderAI`, compile it in MetaEditor, refresh Navigator, and
attach **TraderAI_MultiTimeframeTrend** to each chart/timeframe you want to review. The indicator
does not contain order-placement calls. Its optional common-file log is
`TraderAI-mt5-trend-signals.csv`, and terminal/sound alerts are enabled by default while push
alerts are disabled. Use the chart's normal history controls to inspect earlier arrows and adjust
the inputs for a different instrument or trading horizon.

## Research Strategy Tester EA

`integrations/mt5/TraderAI_ResearchTrendEA.mq5` is installed separately under
`MQL5/Experts/TraderAI` and appears in MT5 Strategy Tester as
**TraderAI_ResearchTrendEA**. It is based on trend-following and time-series-momentum research,
with a prior-range breakout, EMA 20/50, RSI, MACD, ADX, completed H4 bias, ATR exits, risk-sized
volume, and a custom drawdown-aware optimization criterion.

The EA is enabled for simulated Strategy Tester trades but locked from live chart trading by
default. On the connected JustMarkets terminal, use Navigator -> Expert Advisors -> TraderAI,
right-click the EA, and choose **Test**. The full research rationale and a walk-forward testing
checklist are in [Research Strategy Tester EA](research-trend-strategy.md). A short smoke test is
only a runtime check; it is not evidence of future profitability.

### Historical indicator testing

The workstation's `10/90 indicator history` section is a separate historical simulation of the
same M1 rules. It uses the selected symbol's available candles, evaluates only closed candles,
enters at the next candle open, and reports signal count, simulated trades, win rate, net price
return, drawdown, profit factor, total R, and recent trade outcomes.

The test uses the indicator's 0.90 ATR stop and 1.15R target. A position is closed after 15 M1
candles by default, and if a historical candle touches both stop and target, the stop is counted
first. Candle history does not contain the exact spread and commission for every historical fill,
so the report is a rule-validation estimate, not a broker statement or a profit forecast. Use MT5
data for the selected JustMarkets account when the `MT5 data` badge is shown; a `Demo data` badge
means the terminal was unavailable and the test is only an application fallback.

## Adapter Requirements

A production adapter should:

- Read broker symbol metadata from MT5 before placing orders.
- Normalize volume to broker min/max/step.
- Reject symbols that are not visible or tradeable.
- Confirm spreads, session status, stop level, freeze level, and margin impact.
- Place server-side stop loss and take profit with every order.
- Persist every request, broker response, and rejection reason.
- Never bypass the API risk engine.

## Always-On Setup

Use a VPS close to the broker server for reliability. The MT5-connected API must run directly on
the same Windows host as the terminal because the official Python package uses local interprocess
communication. The web app, database, Redis, and observability services can still use Docker.

The Linux API container intentionally skips the Windows-only `MetaTrader5` package and reports the
bridge as unavailable. Do not expect a Linux container to connect directly to a Windows terminal.

Recommended baseline:

- Windows 11 Pro or Windows Server VPS.
- 4 vCPU, 8 GB RAM minimum.
- UPS-backed local PC only if using home hardware.
- Automatic OS updates scheduled outside trading hours.
- Process supervisor or Docker restart policies.
- Daily backups of config, logs, and trade journal data.
