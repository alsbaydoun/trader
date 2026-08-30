# Regime-Aligned Strategy

The active paper strategy is **Regime-Aligned Pullback**, a selective continuation strategy for
closed candles. It is designed to reject the previous failure mode where a single RSI(1) move was
treated as a complete trading signal.

## Entry checklist

An entry needs the complete stack, not just a high score:

- EMA(20) is above EMA(50) for a buy or below it for a sell, with the fast EMA sloping in the
  same direction.
- Directional strength is present: ADX(14) is at least 20 and the matching DI is dominant.
- The prior four candles came back into the EMA zone.
- The latest closed candle breaks the previous candle in the trend direction and closes beyond the
  fast EMA.
- RSI(14) is in the momentum middle zone: 52-68 for a buy or 32-48 for a sell. This avoids
  chasing an already exhausted move.
- Volume is not abnormally thin and ATR is inside the configured volatility band.

If any core condition is missing, the engine returns `WAIT`. Stops use the wider of 1.2 ATR or
0.15% of price, and the target is 1.5 times the stop distance. These values are risk controls,
not a profit claim.

## Extreme scanner safeguard

The RSI(1) 85/15 monitor remains available as a separate alert and paper ledger. RSI(1) is
intentionally reactive, so reaching 85 or 15 is only a watch condition. The extreme paper ledger
requires a rejection candle, RSI(3/7) confirmation, momentum reversal, MACD histogram agreement,
and EMA direction before it can open a virtual trade.

## Measuring it correctly

Use the strategy lab and paper ledger over a meaningful sample. Review win rate together with
profit factor, average R, maximum drawdown, costs, and the result by symbol and timeframe. Do not
promote a strategy because of a short run or because it has a high win rate with large losses.

For MT5 Strategy Tester validation, use real ticks where available, include spread and commission,
and keep a later period out of the parameter search. One-minute OHLC and in-sample optimization
can make a strategy look better than it is.

The revised ledgers use new state files so the older results remain intact for comparison:

- `data/paper-regime-trading.json`
- `data/extreme-pullback-trading.json`

The previous `paper-trading.json` and `extreme-paper-trading.json` files are not deleted or
rewritten.
