# Risk Guardrails

The project is built to reduce accidental live execution and oversized trades. It cannot remove trading risk.

## Default Posture

- Paper trading is the default.
- Signal-only mode is the default UI mode.
- Live trading requires multiple explicit environment values.
- Every executable order requires a stop loss.
- The API rejects orders that exceed configured risk.

## Current Rules

- `MAX_RISK_PER_TRADE_PCT`: maximum account equity risk per order.
- `MAX_DAILY_LOSS_PCT`: daily loss lockout threshold.
- `MAX_OPEN_POSITIONS`: total concurrent position cap.
- `MAX_SYMBOL_EXPOSURE_PCT`: per-symbol exposure cap.
- Stop loss must be present and away from entry.
- `hold` signals cannot be executed.

## Live Trading Unlock

Live trading remains locked unless:

```env
TRADING_MODE=live
LIVE_TRADING_ENABLED=true
BROKER_ADAPTER=mt5
LIVE_TRADING_ACKNOWLEDGEMENT=I understand live trading can lose money
```

Keep the acknowledgement phrase difficult to set by accident. Do not commit real account credentials.

## Operator Checklist

- Run every strategy in paper mode first.
- Review backtest assumptions and slippage.
- Validate symbol contract sizes in MT5.
- Start with the smallest broker-allowed volume.
- Set broker-side stops and account-level drawdown limits.
- Never leave a new strategy unattended with live capital.
