import { useEffect, useRef, useState } from "react";
import {
  Activity,
  BrainCircuit,
  CircleStop,
  Database,
  FlaskConical,
  Play,
  RefreshCcw,
  RotateCcw,
  ShieldCheck
} from "lucide-react";
import type { PaperControl, PaperEquityPoint, PaperPortfolio, PaperTrade } from "../types";

type PaperTab = "open" | "history" | "daily" | "learning" | "log";
type PaperTradingVariant = "market" | "jdub" | "extreme";

interface PaperTradingPanelProps {
  variant?: PaperTradingVariant;
  portfolio?: PaperPortfolio;
  busy: boolean;
  error: string;
  onControl: (control: PaperControl) => void;
  onRun: () => void;
  onClose: (tradeId: string) => void;
  onReset: () => void;
}

export function PaperTradingPanel({
  variant = "market",
  portfolio,
  busy,
  error,
  onControl,
  onRun,
  onClose,
  onReset
}: PaperTradingPanelProps) {
  const [tab, setTab] = useState<PaperTab>("open");
  const extreme = variant === "extreme";
  const jdub = variant === "jdub";
  const engine = portfolio?.engine;
  const metrics = portfolio?.metrics;
  const panelId = extreme ? "extreme-paper-trading" : jdub ? "jdub-trading" : "paper-trading";

  return (
    <section className="paper-workspace" id={panelId} aria-label={extreme ? "Extreme virtual trading" : jdub ? "Jdub Traders virtual trading" : "Virtual paper trading"}>
      <header className="paper-header">
        <div className="paper-title">
          <span className="paper-title-icon"><FlaskConical size={19} /></span>
          <div>
            <h2>{extreme ? "Extreme Virtual Trading" : jdub ? "Jdub Traders" : "Virtual Trading"}</h2>
            <span>{extreme ? "Confirmed 85/15 reversal simulation with no real money" : jdub ? "New York opening-range simulation with no real money" : "Automatic whole-market simulation with no real money"}</span>
          </div>
        </div>
        <div className="paper-actions">
          <label className="paper-toggle">
            <input
              type="checkbox"
              checked={Boolean(engine?.enabled)}
              disabled={busy || !engine}
              onChange={(event) => onControl({ enabled: event.target.checked })}
            />
            <span className="toggle-track" aria-hidden="true"><span /></span>
            <span>{engine?.enabled ? "Auto running" : "Paused"}</span>
          </label>
          <button className="icon-text" type="button" disabled={busy} onClick={onRun}>
            {busy ? <RefreshCcw className="spin" size={15} /> : <Play size={15} />}
            Run now
          </button>
          <button
            className="icon-button"
            type="button"
            title={extreme ? "Reset extreme virtual portfolio" : jdub ? "Reset Jdub Traders virtual portfolio" : "Reset virtual portfolio"}
            aria-label={extreme ? "Reset extreme virtual portfolio" : jdub ? "Reset Jdub Traders virtual portfolio" : "Reset virtual portfolio"}
            disabled={busy}
            onClick={onReset}
          >
            <RotateCcw size={15} />
          </button>
        </div>
      </header>

      <div className={`paper-status ${engine?.last_error || error ? "error" : engine?.enabled ? "running" : ""}`}>
        {engine?.enabled ? <Activity size={15} /> : <CircleStop size={15} />}
        <strong>{engine?.enabled ? "Scanning and simulating" : "Virtual engine paused"}</strong>
        <span>
          {error || engine?.last_error || cycleSummary(portfolio, extreme)}
        </span>
        <b>Virtual only</b>
        {portfolio?.persistence && (
          <b
            className={`paper-save-state ${portfolio.persistence.status}`}
            title="Virtual trades and learning records are stored on the API server."
          >
            <Database size={12} />
            {portfolio.persistence.status === "saved" ? "Saved" : portfolio.persistence.status}
          </b>
        )}
      </div>

      {metrics && engine ? (
        <>
          <div className="paper-metrics" aria-label={extreme ? "Extreme virtual trading performance" : jdub ? "Jdub Traders virtual trading performance" : "Paper trading performance"}>
            <PaperMetric label="Virtual equity" value={money(metrics.equity)} change={metrics.total_return_pct} />
            <PaperMetric label={extreme ? "Profit since signals" : "Net result"} value={signedMoney(metrics.realized_pnl + metrics.unrealized_pnl)} />
            <PaperMetric label="Open / closed" value={`${metrics.open_positions} / ${metrics.closed_trades}`} />
            <PaperMetric label="Win rate" value={`${metrics.win_rate.toFixed(1)}%`} />
            <PaperMetric label="Profit factor" value={metrics.profit_factor?.toFixed(2) ?? "--"} />
            <PaperMetric label="Max drawdown" value={`${metrics.max_drawdown_pct.toFixed(2)}%`} negative />
            <PaperMetric label="Average result" value={`${metrics.average_r_multiple.toFixed(2)}R`} />
            <PaperMetric label="Open risk" value={money(metrics.open_risk_amount)} />
          </div>

          <div className="paper-overview">
            <div className="equity-area">
              <div className="paper-subheading">
                <div>
                  <strong>Equity curve</strong>
                  <span>{portfolio.equity_curve.length} recorded cycles</span>
                </div>
                <div className="equity-legend">
                  <span><i className="equity-line" /> Equity</span>
                  <span><i className="balance-line" /> Closed balance</span>
                </div>
              </div>
              <EquityCurve points={portfolio.equity_curve} startingBalance={metrics.starting_balance} />
            </div>
            <div className="simulation-assumptions">
              <div className="paper-subheading">
                <div>
                  <strong>Simulation rules</strong>
                  <span>{extreme ? "Applied only after RSI(1), MACD, and MA confirmation" : jdub ? "15m New York range, 5m close, then 1m trigger" : "Applied to every eligible directional signal"}</span>
                </div>
              </div>
              <dl>
                <div><dt>Market coverage</dt><dd>{engine.scanned_symbols || "--"} instruments</dd></div>
                <div><dt>Entry filter</dt><dd>{extreme ? `Confirmed 85/15 · score ${engine.minimum_opportunity_score}+` : jdub ? `Opening range · score ${engine.minimum_opportunity_score}+` : engine.minimum_opportunity_score === 0 ? "All strategy signals" : `Score ${engine.minimum_opportunity_score}+`}</dd></div>
                <div><dt>Risk per trade</dt><dd>{engine.risk_per_trade_pct.toFixed(2)}%</dd></div>
                <div><dt>Position limit</dt><dd>{engine.max_open_positions}</dd></div>
                <div><dt>Cycle</dt><dd>{engine.timeframe} / {engine.cycle_interval_seconds}s</dd></div>
                <div><dt>Costs</dt><dd>{money(metrics.fees_paid)} recorded</dd></div>
                <div><dt>Paper learning</dt><dd>{portfolio.learning.observations} outcomes</dd></div>
              </dl>
            </div>
          </div>

          <details className="paper-settings">
            <summary>Simulation controls</summary>
            <div className="paper-settings-grid">
              <label>
                <span>Timeframe</span>
                <select
                  value={engine.timeframe}
                  disabled={busy}
                  onChange={(event) => onControl({ timeframe: event.target.value as PaperControl["timeframe"] })}
                >
                  {(["1m", "5m", "15m", "1h", "4h", "1d"] as const).map((item) => (
                    <option value={item} key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Minimum opportunity score <b>{engine.minimum_opportunity_score.toFixed(0)}</b></span>
                <input
                  type="range"
                  min={extreme ? "70" : jdub ? "50" : "0"}
                  max={extreme || jdub ? "100" : "80"}
                  step="5"
                  value={engine.minimum_opportunity_score}
                  disabled={busy}
                  onChange={(event) => onControl({ minimum_opportunity_score: Number(event.target.value) })}
                />
              </label>
              <label>
                <span>Maximum open positions</span>
                <input
                  type="number"
                  min="1"
                  max="200"
                  value={engine.max_open_positions}
                  disabled={busy}
                  onChange={(event) => onControl({ max_open_positions: Number(event.target.value) })}
                />
              </label>
            </div>
          </details>

          <div className="paper-ledger-heading">
            <div className="segmented paper-tabs" aria-label="Virtual trading records">
              <button className={tab === "open" ? "active" : ""} onClick={() => setTab("open")}>
                Open <span>{metrics.open_positions}</span>
              </button>
              <button className={tab === "history" ? "active" : ""} onClick={() => setTab("history")}>
                History <span>{metrics.closed_trades}</span>
              </button>
              <button className={tab === "daily" ? "active" : ""} onClick={() => setTab("daily")}>
                Daily <span>{portfolio.daily_reports.length}</span>
              </button>
              <button className={tab === "learning" ? "active" : ""} onClick={() => setTab("learning")}>
                Learning <span>{portfolio.learning.observations}</span>
              </button>
              <button className={tab === "log" ? "active" : ""} onClick={() => setTab("log")}>
                Decision log <span>{portfolio.decisions.length}</span>
              </button>
            </div>
            <span className="ledger-update">
              Last cycle {engine.last_cycle_at ? time(engine.last_cycle_at) : "waiting"}
            </span>
          </div>

          {tab === "open" && (
            <OpenTrades trades={portfolio.open_positions} onClose={onClose} busy={busy} extreme={extreme} />
          )}
          {tab === "history" && <TradeHistory trades={portfolio.closed_trades} extreme={extreme} />}
          {tab === "daily" && <DailyReport reports={portfolio.daily_reports} />}
          {tab === "learning" && <LearningPanel learning={portfolio.learning} />}
          {tab === "log" && (
            <div className="decision-log">
              {portfolio.decisions.length ? portfolio.decisions.map((decision) => (
                <article className={`decision-row ${decision.action}`} key={decision.id}>
                  <time>{dateTime(decision.created_at)}</time>
                  <strong>{decision.symbol ?? decision.action}</strong>
                  <span>{decision.outcome}</span>
                  <p>{decision.reason}</p>
                </article>
              )) : <PaperEmpty text="The first scan cycle will create the decision log." />}
            </div>
          )}

          <footer className="paper-footnote">
            <ShieldCheck size={14} />
            <span>{portfolio.disclaimer}</span>
          </footer>
        </>
      ) : (
        <PaperEmpty text="Connecting to the virtual portfolio." />
      )}
    </section>
  );
}

function DailyReport({ reports }: { reports: PaperPortfolio["daily_reports"] }) {
  if (!reports.length) return <PaperEmpty text="Daily results will appear after the first virtual trade closes." />;
  return (
    <div className="daily-report">
      <div className="daily-report-summary">
        <strong>UTC close-day report</strong>
        <span>Only closed virtual trades are included. Amounts include simulated fees.</span>
      </div>
      <div className="paper-table-wrap">
        <table className="paper-table daily-report-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Wins</th>
              <th>Losses</th>
              <th>Win rate</th>
              <th>Win amount</th>
              <th>Loss amount</th>
              <th>Net</th>
              <th>Net %</th>
              <th>Profit factor</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((report) => (
              <tr key={report.date}>
                <td><strong>{reportDate(report.date)}</strong><span>Close day · {money(report.closing_balance)} balance</span></td>
                <td className="positive"><strong>{report.winning_trades}</strong><span>{money(report.winning_amount)} / {report.winning_pct.toFixed(3)}%</span></td>
                <td className="negative"><strong>{report.losing_trades}</strong><span>{money(report.losing_amount)} / {report.losing_pct.toFixed(3)}%</span></td>
                <td>{report.win_rate_pct.toFixed(1)}%</td>
                <td className="positive">{money(report.winning_amount)}</td>
                <td className="negative">{money(report.losing_amount)}</td>
                <td className={pnlClass(report.net_pnl)}><strong>{signedMoney(report.net_pnl)}</strong><span>{money(report.fees_paid)} fees</span></td>
                <td className={pnlClass(report.net_return_pct)}>{report.net_return_pct >= 0 ? "+" : ""}{report.net_return_pct.toFixed(3)}%</td>
                <td>{report.profit_factor?.toFixed(2) ?? "--"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LearningPanel({ learning }: { learning: PaperPortfolio["learning"] }) {
  return (
    <div className="learning-workspace">
      <header className="learning-header">
        <div>
          <strong><BrainCircuit size={15} /> {learning.mode}</strong>
          <span>Losses are recorded as faults; only the paper-entry overlay can adapt.</span>
        </div>
        <span className="learning-count">{learning.observations} outcomes · {learning.wins} wins · {learning.losses} losses</span>
      </header>
      <div className="learning-recommendation">
        <strong>Current recommendation</strong>
        <p>{learning.recommendation}</p>
      </div>
      <div className="learning-plan">
        <strong>How it will adapt next</strong>
        <p>{learning.future_plan}</p>
      </div>
      {learning.last_fault && (
        <div className="learning-fault">
          <strong>Latest fault to review</strong>
          <span>{learning.last_fault}</span>
        </div>
      )}
      {learning.factor_performance.length ? (
        <div className="learning-factor-table">
          {learning.factor_performance.map((factor) => (
            <div className="learning-factor-row" key={factor.factor}>
              <strong>{factor.factor}</strong>
              <span>{factor.samples} samples</span>
              <span>{factor.wins}W / {factor.losses}L</span>
              <b className={factor.win_rate >= 60 ? "positive" : factor.win_rate < 45 ? "negative" : "neutral"}>
                {factor.win_rate.toFixed(1)}%
              </b>
              <span>{factor.average_r_multiple.toFixed(2)}R avg</span>
            </div>
          ))}
        </div>
      ) : (
        <PaperEmpty text="Completed virtual trades will teach the paper overlay which factors deserve more or less weight." />
      )}
      <div className="learning-lessons">
        <div className="learning-lessons-heading">
          <strong>Recent fault lessons</strong>
          <span>Latest non-positive outcomes</span>
        </div>
        {learning.lessons.length ? learning.lessons.map((lesson) => (
          <article className="learning-lesson" key={lesson.trade_id}>
            <header>
              <strong>{lesson.symbol} · {lesson.direction}</strong>
              <span>{dateTime(lesson.observed_at)} · {lesson.r_multiple.toFixed(2)}R · {lesson.exit_reason.replaceAll("_", " ")}</span>
            </header>
            <p><b>Fault</b>{lesson.fault}</p>
            <p><b>Future action</b>{lesson.future_action}</p>
            <div className="learning-factors">{lesson.factors.map((factor) => <span key={factor}>{factor}</span>)}</div>
          </article>
        )) : <PaperEmpty text="Loss lessons will appear after a virtual position closes at or below break-even." />}
      </div>
      <footer className="learning-footnote">
        <ShieldCheck size={13} />
        <span>Learning stays inside paper trading. It never changes the deterministic live strategy or unlocks MT5 orders.</span>
      </footer>
    </div>
  );
}

function OpenTrades({ trades, onClose, busy, extreme }: { trades: PaperTrade[]; onClose: (id: string) => void; busy: boolean; extreme: boolean }) {
  if (!trades.length) return <PaperEmpty text="No actionable signal is open. HOLD signals are observed but never entered." />;
  return (
    <div className="paper-table-wrap">
      <table className="paper-table">
        <thead><tr><th>Market</th><th>{extreme ? "Signal entry / now" : "Entry / current"}</th><th>Stop / target</th><th>Virtual size</th><th>Result</th><th>Signal</th><th>{extreme ? "Since signal" : "Opened"}</th><th /></tr></thead>
        <tbody>{trades.map((trade) => (
          <tr key={trade.id}>
            <td><strong>{trade.symbol}</strong><span className={`side ${trade.direction}`}>{trade.direction}</span></td>
            <td>{price(extreme ? trade.signal_price ?? trade.entry_price : trade.entry_price)}<span>{extreme ? `Fill ${price(trade.entry_price)}` : price(trade.current_price)}</span>{extreme && <small>Now {price(trade.current_price)}</small>}</td>
            <td>{price(trade.stop_loss)}<span>{price(trade.take_profit)}</span></td>
            <td>{trade.quantity.toPrecision(5)}<span>{money(trade.risk_amount)} risk</span></td>
            <td className={pnlClass(trade.unrealized_pnl)}><strong>{signedMoney(trade.unrealized_pnl)}</strong><span>{trade.r_multiple.toFixed(2)}R</span></td>
            <td>{extreme && trade.signal_level ? <strong>{levelLabel(trade.signal_level)}</strong> : `${Math.round(trade.confidence * 100)}%`}<span title={trade.signal_recommendation ?? trade.reasons.join(" ")}>{extreme ? "Confirmed RSI + MACD + MA" : `Score ${trade.opportunity_score.toFixed(1)}`}</span></td>
            <td>{age(signalTime(trade))}<span>{dateTime(signalTime(trade))}</span></td>
            <td><button className="icon-button compact-icon" title="Close virtual position" aria-label={`Close virtual ${trade.symbol} position`} disabled={busy} onClick={() => onClose(trade.id)}><CircleStop size={14} /></button></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function TradeHistory({ trades, extreme }: { trades: PaperTrade[]; extreme: boolean }) {
  if (!trades.length) return <PaperEmpty text="Completed virtual trades will appear here with their full result." />;
  return (
    <div className="paper-table-wrap">
      <table className="paper-table history-table">
        <thead><tr><th>Market</th><th>{extreme ? "Signal / fill / exit" : "Entry / exit"}</th><th>Net result</th><th>Excursion</th><th>Costs</th><th>Exit</th><th>Duration</th></tr></thead>
        <tbody>{trades.map((trade) => (
          <tr key={trade.id}>
            <td><strong>{trade.symbol}</strong><span className={`side ${trade.direction}`}>{trade.direction}</span></td>
            <td>{extreme && trade.signal_level ? levelLabel(trade.signal_level) : price(trade.entry_price)}<span>{extreme ? `${price(trade.signal_price ?? trade.entry_price)} fill ${price(trade.entry_price)}` : price(trade.exit_price)}</span>{extreme && <small>Exit {price(trade.exit_price)}</small>}</td>
            <td className={pnlClass(trade.net_pnl)}><strong>{signedMoney(trade.net_pnl)}</strong><span>{trade.r_multiple.toFixed(2)}R / {trade.return_pct.toFixed(3)}%</span></td>
            <td>{signedMoney(trade.max_favorable_excursion)}<span>{signedMoney(trade.max_adverse_excursion)}</span></td>
            <td>{money(trade.entry_fee + trade.exit_fee)}<span>virtual fees</span></td>
            <td>{exitLabel(trade.exit_reason)}<span>{trade.closed_at ? dateTime(trade.closed_at) : "--"}</span></td>
            <td>{duration(signalTime(trade), trade.closed_at)}<span title={trade.signal_recommendation ?? trade.reasons.join(" ")}>{extreme ? `${dateTime(signalTime(trade))} signal` : `Score ${trade.opportunity_score.toFixed(1)}`}</span></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function EquityCurve({ points, startingBalance }: { points: PaperEquityPoint[]; startingBalance: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const draw = () => drawEquity(canvas, points, startingBalance);
    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [points, startingBalance]);

  return <canvas className="equity-canvas" ref={canvasRef} aria-label="Virtual account equity curve" />;
}

function drawEquity(canvas: HTMLCanvasElement, points: PaperEquityPoint[], startingBalance: number) {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  const context = canvas.getContext("2d");
  if (!context) return;
  context.scale(ratio, ratio);
  context.clearRect(0, 0, rect.width, rect.height);
  const padding = { top: 16, right: 14, bottom: 20, left: 54 };
  const width = Math.max(1, rect.width - padding.left - padding.right);
  const height = Math.max(1, rect.height - padding.top - padding.bottom);
  const values = points.length ? points : [{ timestamp: new Date().toISOString(), equity: startingBalance, balance: startingBalance, unrealized_pnl: 0 }];
  const allValues = values.flatMap((point) => [point.equity, point.balance, startingBalance]);
  const rawMin = Math.min(...allValues);
  const rawMax = Math.max(...allValues);
  const range = Math.max(1, rawMax - rawMin);
  const min = rawMin - range * 0.15;
  const max = rawMax + range * 0.15;
  const x = (index: number) => padding.left + (values.length === 1 ? width : index / (values.length - 1) * width);
  const y = (value: number) => padding.top + (max - value) / (max - min) * height;

  context.strokeStyle = "#26313a";
  context.lineWidth = 1;
  context.fillStyle = "#7f8e9b";
  context.font = "10px system-ui";
  context.textAlign = "right";
  for (let index = 0; index < 4; index += 1) {
    const value = min + (max - min) * (index / 3);
    const lineY = y(value);
    context.beginPath();
    context.moveTo(padding.left, lineY);
    context.lineTo(rect.width - padding.right, lineY);
    context.stroke();
    context.fillText(`$${value.toFixed(0)}`, padding.left - 7, lineY + 3);
  }
  drawLine(context, values.map((point) => point.balance), x, y, "#697785");
  drawLine(context, values.map((point) => point.equity), x, y, "#2ed8a3");
}

function drawLine(
  context: CanvasRenderingContext2D,
  values: number[],
  x: (index: number) => number,
  y: (value: number) => number,
  color: string
) {
  context.beginPath();
  values.forEach((value, index) => {
    if (index === 0) context.moveTo(x(index), y(value));
    else context.lineTo(x(index), y(value));
  });
  context.strokeStyle = color;
  context.lineWidth = 2;
  context.stroke();
}

function PaperMetric({ label, value, change, negative = false }: { label: string; value: string; change?: number; negative?: boolean }) {
  return <div className="paper-metric"><span>{label}</span><strong className={negative ? "negative" : change === undefined ? "" : pnlClass(change)}>{value}</strong>{change !== undefined && <small className={pnlClass(change)}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</small>}</div>;
}

function PaperEmpty({ text }: { text: string }) {
  return <div className="paper-empty"><Activity size={16} /><span>{text}</span></div>;
}

function cycleSummary(portfolio?: PaperPortfolio, extreme = false) {
  const engine = portfolio?.engine;
  if (!engine) return "Loading the virtual portfolio.";
  if (!engine.last_cycle_at) return "The first whole-market simulation cycle is waiting to run.";
  return `${engine.scanned_symbols} scanned, ${engine.eligible_candidates} confirmed, ${engine.opened_last_cycle} opened and ${engine.closed_last_cycle} closed in the last cycle${extreme ? " from threshold signals" : ""}.`;
}

const moneyFormatter = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
function money(value: number) { return moneyFormatter.format(value); }
function signedMoney(value: number) { return `${value > 0 ? "+" : ""}${money(value)}`; }
function pnlClass(value: number) { return value > 0 ? "positive" : value < 0 ? "negative" : "neutral"; }
function price(value: number | null) { return value === null ? "--" : value.toLocaleString(undefined, { maximumFractionDigits: 8 }); }
function time(value: string) { return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value)); }
function dateTime(value: string) { return new Intl.DateTimeFormat(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }
function age(value: string) { const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000)); return seconds < 60 ? `${seconds}s` : seconds < 3600 ? `${Math.floor(seconds / 60)}m` : `${Math.floor(seconds / 3600)}h`; }
function duration(start: string, end: string | null) { if (!end) return age(start); const seconds = Math.max(0, Math.floor((new Date(end).getTime() - new Date(start).getTime()) / 1000)); return seconds < 3600 ? `${Math.max(1, Math.floor(seconds / 60))}m` : `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`; }
function exitLabel(reason: PaperTrade["exit_reason"]) { return reason ? reason.replaceAll("_", " ") : "--"; }
function signalTime(trade: PaperTrade) { return trade.signal_at ?? trade.opened_at; }
function levelLabel(level: string) { return level === "upper_85" ? "85.00 / sell" : level === "lower_15" ? "15.00 / buy" : level; }
function reportDate(value: string) { return new Intl.DateTimeFormat(undefined, { month: "short", day: "2-digit", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`)); }
