import { Activity, BellRing, CircleUserRound, FlaskConical, LayoutGrid, Menu, RefreshCw, ShieldCheck } from "lucide-react";
import type { BrokerAccount, MT5Connection, TradeMode } from "../types";

interface WorkspaceHeaderProps {
  selectedCount: number;
  timeframe: string;
  tradeMode: TradeMode;
  liveUnlocked: boolean;
  brokerAccount?: BrokerAccount | null;
  mt5?: MT5Connection;
  accounts: BrokerAccount[];
  activeAccountId: string | null;
  switchingAccount: boolean;
  scanning: boolean;
  paperEnabled: boolean;
  paperOpenPositions: number;
  extremeAlertCount: number;
  onOpenSymbols: () => void;
  onTimeframeChange: (timeframe: string) => void;
  onAccountChange: (accountId: string) => void;
  onRefresh: () => void;
  onOpenPaper: () => void;
  onOpenExtreme: () => void;
}

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];

export function WorkspaceHeader({
  selectedCount,
  timeframe,
  tradeMode,
  liveUnlocked,
  brokerAccount,
  mt5,
  accounts,
  activeAccountId,
  switchingAccount,
  scanning,
  paperEnabled,
  paperOpenPositions,
  extremeAlertCount,
  onOpenSymbols,
  onTimeframeChange,
  onAccountChange,
  onRefresh,
  onOpenPaper,
  onOpenExtreme
}: WorkspaceHeaderProps) {
  return (
    <header className="workspace-header">
      <div className="brand">
        <button
          className="icon-button menu-button"
          type="button"
          onClick={onOpenSymbols}
          aria-label="Open markets and chart order"
        >
          <Menu size={19} />
        </button>
        <Activity size={25} />
        <div>
          <h1>Trader AI Workstation</h1>
          <span>paper-first scanner and execution console</span>
        </div>
      </div>

      <div className="header-controls">
        <div className="segmented compact">
          {TIMEFRAMES.map((option) => (
            <button
              key={option}
              className={timeframe === option ? "active" : ""}
              type="button"
              onClick={() => onTimeframeChange(option)}
            >
              {option}
            </button>
          ))}
        </div>

        <button className="icon-text" type="button" onClick={onRefresh}>
          <RefreshCw size={16} className={scanning ? "spin" : ""} />
          Scan
        </button>
        <button className="icon-text pair-count" type="button" onClick={onOpenSymbols}>
          <LayoutGrid size={15} />
          {selectedCount} charts
        </button>
        <button className="icon-text paper-jump" type="button" onClick={onOpenPaper}>
          <FlaskConical size={15} />
          Paper {paperOpenPositions}
        </button>
        <button className="icon-text extreme-jump" type="button" onClick={onOpenExtreme}>
          <BellRing size={15} />
          Alerts {extremeAlertCount}
        </button>
      </div>

      <div className="status-pill">
        {brokerAccount?.profile_configured && (
          <div className="account-switcher">
            <CircleUserRound size={15} />
            <label className="sr-only" htmlFor="account-select">Trading account</label>
            <select
              id="account-select"
              value={activeAccountId ?? ""}
              disabled={switchingAccount}
              onChange={(event) => onAccountChange(event.target.value)}
            >
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.provider} {account.account_type} {account.login_masked}
                </option>
              ))}
            </select>
            <span
              className={
                mt5?.connection_verified
                  ? "account-state ready"
                  : mt5?.status === "account_mismatch" || mt5?.status === "server_mismatch"
                    ? "account-state error"
                    : "account-state pending"
              }
              title={mt5?.message ?? "Checking the local MetaTrader 5 connection"}
            >
              {mt5?.connection_verified
                ? "Connected"
                : mt5?.status === "account_mismatch"
                  ? "MT5 mismatch"
                  : "Read-only"}
            </span>
          </div>
        )}
        <FlaskConical size={15} />
        <span>{paperEnabled && tradeMode === "auto_trade" ? "Virtual auto" : "Signals only"}</span>
        <ShieldCheck size={15} />
        <span>{liveUnlocked ? "Live unlocked" : "Real money locked"}</span>
      </div>
    </header>
  );
}
