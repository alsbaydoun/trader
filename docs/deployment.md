# Deployment Guide

## Local Development

Start the API:

```bash
cd services/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Start the UI:

```bash
cd apps/web
npm install
npm run dev
```

## Docker Deployment

```bash
cp .env.example .env
docker compose up --build -d
```

Use paper trading first. Confirm `/status` reports `live_trading_unlocked: false` unless you intentionally enabled live mode.
Keep `data/paper-trading.json`, `data/extreme-paper-trading.json`, and their `.bak` files on persistent
storage. They contain the regular and extreme virtual trade histories, equity curves, decision logs,
and paper-learning profiles. The extreme scanner can continue marking open virtual trades after a
restart because its ledger is independent and persisted on the API host.

## Production Notes

- Put the stack behind a private VPN or authenticated reverse proxy.
- Use HTTPS for any remote access.
- Store secrets in a secrets manager or deployment platform, not in Git.
- Add persistent storage for PostgreSQL and Grafana.
- Configure log retention and export.
- Add backups before storing real trade journals.

## Android Access

When the UI is running on a Windows PC or VPS, connect from the Samsung S24 Ultra through the same private network or VPN and open the web URL. The layout collapses into a single-column mobile view while preserving charts, alerts, reasons, and mode controls.

## Windows Always-On Startup

For the local Windows 11 setup that talks to MetaTrader 5, use the Windows helper scripts:

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\start-trader.ps1 -OpenBrowser
```

To start the workstation automatically after Windows sign-in:

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\install-startup-task.ps1
```

Useful checks:

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\status-trader.ps1
powershell -ExecutionPolicy Bypass -File .\ops\windows\stop-trader.ps1
```

This keeps the local web app and API available while the Windows session is active. MT5 must also
remain open and signed into the account you want the workstation to read.

## Best Non-Stop Setup

For serious 24/7 operation, run the system on a Windows VPS instead of a home PC. The VPS should
run MetaTrader 5, the API, the web app, and the startup task in the same Windows session. Use a
private VPN or authenticated HTTPS proxy for remote access from Android and Windows. Keep live
trading disabled until paper results, risk settings, and broker permissions have been reviewed.
