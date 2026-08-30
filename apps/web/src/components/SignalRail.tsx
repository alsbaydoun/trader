import { Bell, Landmark, ListTree, MessageSquareText, ShieldAlert, Volume2 } from "lucide-react";
import type {
  Backtest,
  ExtremeBacktest,
  ExtremeBacktestTrade,
  MarketEvent,
  MT5Connection,
  MT5Quote,
  NewsStatus,
  Signal,
  StrategyDefinition,
  TradeMode
} from "../types";
import { NewsAnalysisPanel } from "./NewsAnalysisPanel";

interface SignalRailProps {
  activeSignal?: Signal;
  backtest?: Backtest;
  extremeBacktest?: ExtremeBacktest;
  extremeHistoryLimit: number;
  timeframe: string;
  events: MarketEvent[];
  newsStatus?: NewsStatus;
  activeSymbol: string;
  strategy?: StrategyDefinition;
  tradeMode: TradeMode;
  liveUnlocked: boolean;
  mt5?: MT5Connection;
  mt5Quotes: MT5Quote[];
  soundEnabled: boolean;
  voiceEnabled: boolean;
  onTradeModeChange: (mode: TradeMode) => void;
  onSoundToggle: () => void;
  onVoiceToggle: () => void;
  onExtremeHistoryLimitChange: (limit: number) => void;
}

export function SignalRail({
  activeSignal,
  backtest,
  extremeBacktest,
  extremeHistoryLimit,
  timeframe,
  events,
  newsStatus,
  activeSymbol,
  strategy,
  tradeMode,
  liveUnlocked,
  mt5,
  mt5Quotes,
  soundEnabled,
  voiceEnabled,
  onTradeModeChange,
  onSoundToggle,
  onVoiceToggle,
  onExtremeHistoryLimitChange
}: SignalRailProps) {
  return (
    <aside className="signal-rail">
      <section className="rail-block mt5-account">
        <div className="section-heading">
          <Landmark size={17} />
          <h2>MT5 Account</h2>
          <span className="read-only-badge">Read-only</span>
        </div>
        {mt5 ? (
          <>
            <div
              className={
                mt5.connection_verified
                  ? "connection-banner connected"
                  : mt5.status === "account_mismatch" || mt5.status === "server_mismatch"
                    ? "connection-banner error"
                    : "connection-banner"
              }
            >
              <strong>
                {mt5.connection_verified
                  ? "Connected"
                  : mt5.status === "account_mismatch"
                    ? "Account mismatch"
                    : "Waiting for MT5"}
              </strong>
              <span>{mt5.terminal_server || "Local terminal"}</span>
            </div>
            <p className="guardrail-copy">{mt5.message}</p>
            {mt5.status === "account_mismatch" && (
              <div className="account-match-grid">
                <span>Workstation <strong>{mt5.selected_login_masked}</strong></span>
                <span>MT5 terminal <strong>{mt5.terminal_login_masked}</strong></span>
              </div>
            )}
            {mt5.connection_verified && (
              <>
                <div className="metrics-grid account-metrics">
                  <Metric label="Balance" value={formatMoney(mt5.balance, mt5.currency)} />
                  <Metric label="Equity" value={formatMoney(mt5.equity, mt5.currency)} />
                  <Metric label="Free margin" value={formatMoney(mt5.margin_free, mt5.currency)} />
                  <Metric label="Open positions" value={mt5.positions_count.toString()} />
                </div>
                {mt5Quotes.length > 0 && (
                  <div className="quote-list" aria-label="Live MT5 quotes">
                    {mt5Quotes.slice(0, 4).map((quote) => (
                      <div className="quote-row" key={quote.symbol}>
                        <strong title={`JustMarkets symbol: ${quote.symbol}`}>{quote.requested_symbol}</strong>
                        <span>{quote.bid.toFixed(quote.digits)}</span>
                        <span>{quote.ask.toFixed(quote.digits)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        ) : (
          <p className="muted">Checking the local MetaTrader 5 terminal.</p>
        )}
      </section>

      <section className="rail-block">
        <div className="section-heading">
          <MessageSquareText size={17} />
          <h2>Signal</h2>
          {activeSignal && (
            <span className={`source-badge ${activeSignal.source}`}>
              {activeSignal.source === "mt5" ? "MT5 data" : "Demo data"}
            </span>
          )}
        </div>
        {activeSignal ? (
          <>
            <div className={`signal-badge ${activeSignal.direction}`}>
              <span>{activeSignal.symbol}</span>
              <strong>{activeSignal.direction}</strong>
              <span>{Math.round(activeSignal.confidence * 100)}%</span>
            </div>
            <div className="levels">
              <span>Entry {activeSignal.entry}</span>
              <span>Stop {activeSignal.stop_loss ?? "--"}</span>
              <span>Target {activeSignal.take_profit ?? "--"}</span>
            </div>
            <div className="reason-list">
              {activeSignal.reasons.map((reason) => (
                <article key={`${reason.category}-${reason.message}`} className={`reason ${reason.impact}`}>
                  <strong>{reason.category}</strong>
                  <p>{reason.message}</p>
                </article>
              ))}
            </div>
          </>
        ) : (
          <p className="muted">Waiting for scanner data.</p>
        )}
      </section>

      <section className="rail-block strategy-block">
        <div className="section-heading">
          <ListTree size={17} />
          <h2>Active Strategy</h2>
          {strategy && <span className="read-only-badge">Rules v{strategy.version}</span>}
        </div>
        {strategy ? (
          <>
            <strong>{strategy.name}</strong>
            <p className="guardrail-copy">{strategy.summary}</p>
            <div className="strategy-components">
              {strategy.components.map((component, index) => (
                <span key={component}><b>{index + 1}</b>{component}</span>
              ))}
            </div>
            <details className="strategy-details">
              <summary>Entry and risk rules</summary>
              <p><strong>Entry:</strong> score at least {strategy.entry_threshold}</p>
              <p><strong>Stop:</strong> {strategy.stop_model}</p>
              <p><strong>Target:</strong> {strategy.target_model}</p>
              <p>{strategy.caveat}</p>
            </details>
          </>
        ) : (
          <p className="muted">Loading the active strategy.</p>
        )}
      </section>

      <NewsAnalysisPanel
        activeSymbol={activeSymbol}
        events={events}
        status={newsStatus}
      />

      <section className="rail-block">
        <div className="section-heading">
          <ShieldAlert size={17} />
          <h2>Execution</h2>
        </div>
        <div className="segmented">
          <button
            className={tradeMode === "signal_only" ? "active" : ""}
            type="button"
            onClick={() => onTradeModeChange("signal_only")}
          >
            Signals only
          </button>
          <button
            className={tradeMode === "auto_trade" ? "active" : ""}
            type="button"
            onClick={() => onTradeModeChange("auto_trade")}
          >
            Auto virtual
          </button>
        </div>
        <p className="guardrail-copy">
          {liveUnlocked
            ? "Virtual automation is separate. The server reports live trading unlocked, so review configuration before using any real-order endpoint."
            : "Auto virtual simulates eligible trades only. Real MT5 order placement remains locked."}
        </p>
      </section>

      <section className="rail-block">
        <div className="section-heading">
          <Bell size={17} />
          <h2>Alerts</h2>
        </div>
        <div className="toggle-row">
          <button className={soundEnabled ? "toggle on" : "toggle"} type="button" onClick={onSoundToggle}>
            <Volume2 size={15} />
            Sound
          </button>
          <button className={voiceEnabled ? "toggle on" : "toggle"} type="button" onClick={onVoiceToggle}>
            Voice
          </button>
        </div>
      </section>

      <section className="rail-block">
        <div className="section-heading">
          <h2>Backtest</h2>
          {backtest && (
            <span className={`source-badge ${backtest.source}`}>
              {backtest.source === "mt5" ? "MT5 data" : "Demo data"}
            </span>
          )}
        </div>
        {backtest ? (
          <div className="metrics-grid">
            <Metric label="Trades" value={backtest.trades.toString()} />
            <Metric label="Win rate" value={`${Math.round(backtest.win_rate * 100)}%`} />
            <Metric label="Net" value={`${backtest.net_return_pct}%`} />
            <Metric label="Drawdown" value={`${backtest.max_drawdown_pct}%`} />
          </div>
        ) : (
          <p className="muted">Run data is loading.</p>
        )}
      </section>

      <section className="rail-block extreme-history-block">
        <div className="section-heading">
          <h2>10/90 indicator history</h2>
          {extremeBacktest && (
            <span className={`source-badge ${extremeBacktest.source}`}>
              {extremeBacktest.source === "mt5" ? "MT5 data" : "Demo data"}
            </span>
          )}
        </div>
        {timeframe !== "1m" ? (
          <p className="muted">This MT5 indicator history test is available on M1 only. Switch the chart timeframe to M1 to run it.</p>
        ) : extremeBacktest ? (
          <>
            <p className="backtest-window">
              {extremeBacktest.symbol} M1 · {extremeBacktest.bars_tested.toLocaleString()} bars · {formatDate(extremeBacktest.data_start)} to {formatDate(extremeBacktest.data_end)}
            </p>
            <div className="history-range-control">
              <span>History depth</span>
              <div className="segmented compact" role="group" aria-label="Historical bar count">
                {[2000, 5000, 10000].map((limit) => (
                  <button
                    className={extremeHistoryLimit === limit ? "active" : ""}
                    key={limit}
                    type="button"
                    title={`Test the last ${limit.toLocaleString()} M1 bars`}
                    onClick={() => onExtremeHistoryLimitChange(limit)}
                  >
                    {limit >= 1000 ? `${limit / 1000}K` : limit}
                  </button>
                ))}
              </div>
            </div>
            <div className="metrics-grid">
              <Metric label="Signals" value={extremeBacktest.signals.toString()} />
              <Metric label="Win rate" value={`${Math.round(extremeBacktest.win_rate * 100)}%`} />
              <Metric label="Net return" value={`${extremeBacktest.net_return_pct}%`} />
              <Metric label="Drawdown" value={`${extremeBacktest.max_drawdown_pct}%`} />
              <Metric label="Profit factor" value={extremeBacktest.profit_factor?.toString() ?? "--"} />
              <Metric label="Total R" value={`${extremeBacktest.total_r}R`} />
            </div>
            <details className="history-details">
              <summary>View recent simulated trades</summary>
              {extremeBacktest.trades_detail.length ? (
                <div className="history-trade-list">
                  {extremeBacktest.trades_detail.slice(0, 8).map((trade) => (
                    <div className="history-trade-row" key={`${trade.signal_at}-${trade.direction}`}>
                      <div>
                        <strong className={trade.direction}>{trade.direction.toUpperCase()}</strong>
                        <span>{formatDate(trade.signal_at)}</span>
                      </div>
                      <div>
                        <strong className={trade.outcome === "win" ? "positive" : trade.outcome === "loss" ? "negative" : ""}>
                          {trade.r_multiple >= 0 ? "+" : ""}{trade.r_multiple}R
                        </strong>
                        <span>{formatExitReason(trade.exit_reason)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">No confirmed 10/90 entries were found in this history window.</p>
              )}
            </details>
            <details className="history-details">
              <summary>Rules and test assumptions</summary>
              <ul className="history-assumptions">
                {extremeBacktest.assumptions.map((assumption) => <li key={assumption}>{assumption}</li>)}
              </ul>
            </details>
          </>
        ) : (
          <p className="muted">Historical indicator data is loading.</p>
        )}
      </section>

    </aside>
  );
}

function formatMoney(value: number | null, currency: string): string {
  if (value === null) return "--";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency || "USD",
    maximumFractionDigits: 2
  }).format(value);
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function formatExitReason(reason: ExtremeBacktestTrade["exit_reason"]): string {
  return reason.replaceAll("_", " ");
}
