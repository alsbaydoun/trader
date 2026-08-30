# Research Strategy Tester EA

## Research conclusion

There is no verified strategy that always wins, and a public claim of high win rate is not
enough evidence to copy a system. For this workstation, the most defensible starting point is a
trend-following and breakout strategy with volatility-normalized risk. The research basis is
time-series momentum: the published study by Moskowitz, Ooi, and Pedersen found return
continuation across liquid equity-index, currency, commodity, and bond futures, while also noting
that sharp trend reversals can hurt trend-following systems.

This is a better fit for the workstation's multi-timeframe design than assuming every RSI extreme
must reverse. The EA still uses momentum confirmation and an optional higher-timeframe bias, but it
enters only after a completed candle breaks the prior range.

Relevant references:

- [Time Series Momentum](https://doi.org/10.1016/j.jfineco.2011.11.003), Journal of Financial Economics.
- [Testing Trading Strategies](https://www.mql5.com/en/docs/runtime/testing), MQL5 Reference.
- [OnTester custom optimization criterion](https://www.mql5.com/en/docs/event_handlers/ontester), MQL5 Reference.
- [ESMA CFD investor protection warning](https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-investors), which reports that 74-89% of retail CFD accounts typically lost money in the jurisdictions reviewed.

## Implemented EA

`integrations/mt5/TraderAI_ResearchTrendEA.mq5` is a standalone Expert Advisor for MT5 Strategy
Tester. Its default signal requires all of the following on the last completed entry-timeframe
candle:

- Close beyond the previous 20-bar high or low.
- EMA 20/50 trend alignment.
- RSI(14) at least 55 for long trades or at most 45 for short trades.
- MACD histogram aligned with the direction and increasing in magnitude.
- ADX(14) at least 18 and directional-index agreement.
- Completed H4 close on the correct side of its EMA when the bias filter is enabled.

Stops are based on 1.5 ATR, targets default to 2R, and position size risks 0.25% of equity before
broker constraints. Break-even, ATR trailing, maximum holding bars, one-position limits,
cooldown, session, spread, and broker minimum-volume checks are included. The EA records signal
and trade context in the common files area and exposes a drawdown-aware `OnTester()` score for
optimization. It rejects optimization candidates with fewer than 30 trades by default.

## Safety boundary

`EnableStrategyTesterTrading=true` and `EnableLiveTrading=false` are the defaults. In Strategy
Tester, MT5 simulates the EA's trades. On a normal chart in the connected JustMarkets terminal,
the EA stays signal-only and displays `SIGNAL ONLY - LIVE ORDERS LOCKED`. Live trading additionally
requires setting the acknowledgement input exactly to `I UNDERSTAND LIVE TRADING RISK` and is not
part of the workstation's default deployment.

The EA contains order calls because Strategy Tester needs simulated orders to calculate entries,
exits, drawdown, and costs. Those calls are unreachable on a normal chart until the separate live
inputs are deliberately changed. Keep the existing `TRADING_MODE=paper` application settings in
place as well.

## Recommended tester workflow

1. In MT5, open `Navigator -> Expert Advisors -> TraderAI`, right-click
   **TraderAI_ResearchTrendEA**, and choose **Test**.
2. Select the exact broker symbol, including suffixes such as `.m` or `.std`, and test each
   timeframe separately. M15, H1, and H4 are useful starting points; M1 is more sensitive to
   spread and execution assumptions.
3. Use `Every tick based on real ticks` when that option is available. Otherwise use `Every tick`.
   MQL5 documents `Every tick` as the most detailed standard modelling mode; OHLC and open-price
   modes are faster approximations and can change stop/target results.
4. Use a long historical range. Keep an in-sample period for designing parameters, a later
   untouched out-of-sample period, and a forward period. Do not optimize only for total profit or
   win rate; reject settings that work only on one symbol, one date range, or one spread.
5. Review history quality, number of trades, profit factor, expected payoff after costs, maximum
   equity drawdown, losing streaks, and stability across symbols. A high win rate with a large
   average loss is not automatically safer.
6. If optimizing, use the EA's `Custom max` criterion after confirming that the candidate has
   enough trades. The criterion rewards net profit and profit factor while penalizing relative
   equity drawdown; it is a ranking aid, not a guarantee.

The first local smoke test was EURUSD.m on H1 for the last month: 456 bars, 100% history quality,
9 trades, 6 winners, 1.68 profit factor, and 0.58% maximum equity drawdown. It confirms that the
EA runs and reports correctly; it is not a statistically meaningful performance claim.
