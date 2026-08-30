# Operations Runbook

## Daily Startup

1. Confirm broker and data-feed status.
2. Confirm `TRADING_MODE=paper` unless a deliberate live session is planned.
3. Review open positions and daily loss state.
4. Start the scanner.
5. Watch API health, scanner logs, and Prometheus metrics.

On Windows, start the local workstation with:

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\start-trader.ps1 -OpenBrowser
```

Check it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\status-trader.ps1
```

## Incident Response

- If alerts become noisy, switch the UI to signal-only mode and disable voice.
- If drawdown approaches the daily limit, stop auto execution and review logs.
- If broker rejects orders, verify symbol suffix, market session, min volume, margin, and stop distance.
- If data feed stalls, block order placement and fail closed.
- If the website cannot be reached on `http://127.0.0.1:5173/`, check status and rerun the Windows
  start script. A reboot, closed terminal, Windows sleep, or killed background process can stop the
  local development servers.

## Observability

The API exposes:

- `/health` for service health.
- `/metrics` for Prometheus scraping.
- `trader_signals_generated_total`.
- `trader_orders_rejected_total`.
- `trader_open_positions`.

Add dashboards for:

- Signal frequency by symbol.
- Risk rejections by reason.
- Open position count.
- API latency.
- Scanner loop freshness.
