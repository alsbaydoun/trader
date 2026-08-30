# Whole-Market Scanner

The left Markets drawer is independent from the open chart grid. Removing a chart changes only the
workspace; the instrument remains part of the broker-wide scan.

## Universe

When the selected MT5 account is verified, `/market/symbols` enumerates every tradeable instrument
returned by that JustMarkets terminal. The workstation currently sees 272 instruments on the
configured Standard account, but the count is account- and broker-dependent.

The first scan loads 120 candles for each available instrument and may take around 30 seconds.
Results are cached for five minutes. The browser loads selected charts first, starts the full scan
in the background, and refreshes it every five minutes. The drawer refresh button can force a new
scan.

## Ranking

The ranking is an opportunity score, not a profit forecast. It combines:

- Current deterministic signal confidence.
- Whether the signal is directional or hold.
- Estimated target distance as a percentage of entry.
- Current bid/ask spread as a cost penalty.
- Quote freshness and active-market state.

Active markets are always sorted ahead of inactive markets. Stale or zero quotes receive a large
penalty and are labeled `Market inactive`. The ranked list includes the score, direction, and the
underlying signal reasons. Every candidate remains subject to the risk engine and paper-first
execution controls.

## Chart Management

Use the left menu to search the broker catalog and add a chart. Open charts can be removed or
dragged into a new order. The ordered list is saved in browser local storage for that device.
Changing chart order does not place, modify, or close any broker trade.
