import { useEffect, useState } from "react";
import {
  BrainCircuit,
  CheckCircle2,
  CircleStop,
  FlaskConical,
  Play,
  RefreshCcw,
  ShieldCheck,
  Target
} from "lucide-react";
import type { PaperControl, StrategyLabMember, StrategyLabSnapshot } from "../types";

interface StrategyLabPanelProps {
  snapshot?: StrategyLabSnapshot;
  busy: boolean;
  error: string;
  onRun: () => void;
  onControl: (strategyId: string, control: PaperControl) => void;
}

export function StrategyLabPanel({ snapshot, busy, error, onRun, onControl }: StrategyLabPanelProps) {
  const [activeId, setActiveId] = useState("");
  const active = snapshot?.strategies.find((strategy) => strategy.id === activeId)
    ?? snapshot?.strategies[0];

  useEffect(() => {
    if (snapshot?.strategies.length && !snapshot.strategies.some((strategy) => strategy.id === activeId)) {
      setActiveId(snapshot.strategies[0].id);
    }
  }, [activeId, snapshot?.strategies]);

  return (
    <section className="strategy-lab-workspace" id="strategy-lab" aria-label="M1 paper strategy lab">
      <header className="strategy-lab-header">
        <div className="strategy-lab-title">
          <span className="strategy-lab-title-icon"><FlaskConical size={19} /></span>
          <div>
            <h2>M1 Scalp Strategy Lab</h2>
            <span>Competing paper-only rules learn from the same live MT5 observations</span>
          </div>
        </div>
        <button className="icon-text" type="button" disabled={busy} onClick={onRun}>
          {busy ? <RefreshCcw className="spin" size={15} /> : <Play size={15} />}
          Run all now
        </button>
      </header>

      <div className={`strategy-lab-status ${error ? "error" : ""}`}>
        {error ? <CircleStop size={15} /> : <BrainCircuit size={15} />}
        <strong>{error ? "Strategy lab error" : "Paper comparison active"}</strong>
        <span>{error || statusText(snapshot)}</span>
        <b>Virtual only</b>
      </div>

      {snapshot?.strategies.length ? (
        <>
          <div className="segmented strategy-lab-tabs" role="tablist" aria-label="Paper scalp strategies">
            {snapshot.strategies.map((strategy) => (
              <button
                className={active?.id === strategy.id ? "active" : ""}
                key={strategy.id}
                type="button"
                role="tab"
                aria-selected={active?.id === strategy.id}
                onClick={() => setActiveId(strategy.id)}
              >
                <span>{strategy.name}</span>
                <small>{strategy.portfolio.metrics.win_rate.toFixed(1)}% wins</small>
              </button>
            ))}
          </div>

          {active && <StrategyDetail strategy={active} busy={busy} onControl={onControl} />}

          <div className="strategy-lab-lessons">
            <div className="strategy-lab-subheading">
              <strong><BrainCircuit size={15} /> Main head lessons</strong>
              <span>Evidence is collected separately from each paper ledger</span>
            </div>
            <div className="strategy-lesson-list">
              {snapshot.main_lessons.map((lesson) => <p key={lesson}>{lesson}</p>)}
            </div>
          </div>
        </>
      ) : (
        <div className="strategy-lab-empty">The paper strategy lab is waiting for its first M1 scan.</div>
      )}

      <footer className="strategy-lab-footnote">
        <ShieldCheck size={14} />
        <span>{snapshot?.disclaimer ?? "No live orders are placed by the strategy lab."}</span>
      </footer>
    </section>
  );
}

function StrategyDetail({
  strategy,
  busy,
  onControl
}: {
  strategy: StrategyLabMember;
  busy: boolean;
  onControl: (strategyId: string, control: PaperControl) => void;
}) {
  const { engine, metrics, learning } = strategy.portfolio;
  return (
    <div className="strategy-lab-detail" role="tabpanel">
      <div className="strategy-lab-detail-heading">
        <div>
          <h3>{strategy.name}</h3>
          <p>{strategy.summary}</p>
        </div>
        <label className="paper-toggle">
          <input
            type="checkbox"
            checked={engine.enabled}
            disabled={busy}
            onChange={(event) => onControl(strategy.id, { enabled: event.target.checked })}
          />
          <span className="toggle-track" aria-hidden="true"><span /></span>
          <span>{engine.enabled ? "Auto running" : "Paused"}</span>
        </label>
      </div>

      <div className="strategy-lab-metrics">
        <LabMetric label="Virtual equity" value={money(metrics.equity)} />
        <LabMetric label="Net result" value={signedMoney(metrics.realized_pnl + metrics.unrealized_pnl)} tone={metrics.realized_pnl + metrics.unrealized_pnl} />
        <LabMetric label="Closed / open" value={`${metrics.closed_trades} / ${metrics.open_positions}`} />
        <LabMetric label="Win rate" value={`${metrics.win_rate.toFixed(1)}%`} tone={metrics.win_rate - 50} />
        <LabMetric label="Profit factor" value={metrics.profit_factor?.toFixed(2) ?? "--"} />
        <LabMetric label="Drawdown" value={`${metrics.max_drawdown_pct.toFixed(2)}%`} tone={-metrics.max_drawdown_pct} />
      </div>

      <div className="strategy-lab-rule-grid">
        <div>
          <div className="strategy-lab-subheading"><strong><Target size={14} /> Entry rules</strong><span>{strategy.candidates_last_cycle} confirmed this cycle</span></div>
          <ul>{strategy.criteria.map((criterion) => <li key={criterion}><CheckCircle2 size={13} />{criterion}</li>)}</ul>
        </div>
        <dl>
          <div><dt>Timeframe</dt><dd>{engine.timeframe}</dd></div>
          <div><dt>Stop model</dt><dd>{strategy.stop_atr.toFixed(2)} ATR</dd></div>
          <div><dt>Target model</dt><dd>{strategy.target_r.toFixed(2)}R</dd></div>
          <div><dt>Max hold</dt><dd>{strategy.max_minutes} minutes</dd></div>
          <div><dt>Paper learning</dt><dd>{learning.observations} outcomes</dd></div>
        </dl>
      </div>

      <div className="strategy-lab-trades">
        <div className="strategy-lab-subheading"><strong>Recent paper outcomes</strong><span>Signal to exit detail</span></div>
        {strategy.portfolio.closed_trades.length ? (
          <div className="strategy-lab-trade-list">
            {strategy.portfolio.closed_trades.slice(0, 5).map((trade) => (
              <div className="strategy-lab-trade-row" key={trade.id}>
                <strong>{trade.symbol}</strong>
                <span className={`side ${trade.direction}`}>{trade.direction}</span>
                <span>{trade.r_multiple.toFixed(2)}R</span>
                <b className={trade.net_pnl >= 0 ? "positive" : "negative"}>{signedMoney(trade.net_pnl)}</b>
                <small>{trade.exit_reason?.replaceAll("_", " ") ?? "--"}</small>
              </div>
            ))}
          </div>
        ) : (
          <p className="strategy-lab-empty">No completed outcomes yet. The lab will record every virtual entry and exit.</p>
        )}
      </div>
    </div>
  );
}

function LabMetric({ label, value, tone }: { label: string; value: string; tone?: number }) {
  return <div className="strategy-lab-metric"><span>{label}</span><strong className={tone === undefined ? "" : tone >= 0 ? "positive" : "negative"}>{value}</strong></div>;
}

function statusText(snapshot?: StrategyLabSnapshot): string {
  if (!snapshot) return "Connecting to the M1 paper strategy lab.";
  if (snapshot.source !== "mt5") return "Waiting for verified MT5 market data.";
  const closed = snapshot.strategies.reduce((total, strategy) => total + strategy.portfolio.metrics.closed_trades, 0);
  return `${snapshot.strategies.length} strategies are scanning ${snapshot.timeframe}; ${closed} completed paper outcomes recorded.`;
}

const moneyFormatter = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
function money(value: number) { return moneyFormatter.format(value); }
function signedMoney(value: number) { return `${value > 0 ? "+" : ""}${money(value)}`; }
