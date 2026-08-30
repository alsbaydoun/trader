# News Analysis

The news workspace is analysis-first. Headline text is supporting evidence; it is not presented as
a trading instruction.

## What the Workstation Explains

Each verified event can include:

- Global market interpretation and event severity.
- Related symbols and expected bullish, bearish, mixed, or neutral impact.
- Confidence and expected time horizon.
- The causal chain from the release to USD, yields, liquidity, demand, or supply.
- Bullish and bearish surprise scenarios before a release.
- Actual, forecast, and previous values when available.
- Invalidation conditions and a spread/volatility risk window.
- Provider, source URL, freshness, and calendar/headline coverage state.

Future events are always conditional. The system does not assign a known direction before the
actual value, revisions, and cross-market confirmation arrive.

## Current Sources

### MT5 Economic Calendar

`TraderCalendarBridge.mq5` calls the native MQL5 calendar functions inside MetaTrader 5 and writes
a UTF-8 CSV file to `FILE_COMMON`. The API reads that file without controlling the terminal and
without storing an MT5 password.

The exporter currently requests USD events from 24 hours in the past through seven days in the
future. That covers the most important common drivers for gold, silver, Bitcoin, US indices, and
energy CFDs, including inflation, labor, central-bank, growth, and oil-inventory events.

### Unscheduled Headlines

The MT5 Python integration cannot retrieve the JustMarkets/MT5 News-tab articles. A licensed
headline provider is required for unscheduled central-bank comments, geopolitical events, company
news, crypto news, and supply disruptions. Until such a provider is configured, the UI explicitly
shows `Headlines` as missing and does not generate fake live analysis.

Add a provider behind `NewsService` and preserve the normalized `MarketEvent` and `MarketImpact`
contracts. Keep API keys in environment variables or a secret manager; never commit them.

## Analysis Rules

The current deterministic engine maps common event families to cross-asset transmission rules:

- Inflation, labor, and central-bank surprises affect USD and rate expectations, then metals,
  Bitcoin, and US equity indices.
- Growth releases can have conflicting rate and demand effects, so the engine uses `mixed` when a
  single directional claim would be misleading.
- Oil-inventory surprises primarily affect WTI and Brent through the prompt supply balance.
- Price, yields, USD, spreads, and revisions are explicit confirmation or invalidation inputs.

These are hypotheses for decision support. They do not guarantee that the market will follow its
historical relationship on a given release.
