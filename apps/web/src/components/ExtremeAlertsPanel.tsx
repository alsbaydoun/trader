import { useState } from "react";
import { BellRing, ChevronDown, Clock3, Radio, ShieldAlert, Volume2 } from "lucide-react";
import type { ExtremeAlert, ExtremeReading, ExtremeScan } from "../types";

interface ExtremeAlertsPanelProps {
  scan?: ExtremeScan;
  busy: boolean;
  soundEnabled: boolean;
  voiceEnabled: boolean;
  upper85NotificationsEnabled: boolean;
  lower15NotificationsEnabled: boolean;
  onUpper85NotificationsToggle: (enabled: boolean) => void;
  onLower15NotificationsToggle: (enabled: boolean) => void;
  onRun: () => void;
}

export function ExtremeAlertsPanel({
  scan,
  busy,
  soundEnabled,
  voiceEnabled,
  upper85NotificationsEnabled,
  lower15NotificationsEnabled,
  onUpper85NotificationsToggle,
  onLower15NotificationsToggle,
  onRun
}: ExtremeAlertsPanelProps) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const alerts = scan?.alerts ?? [];
  const extremes = scan?.readings.filter((reading) => reading.level !== "neutral").slice(0, 12) ?? [];

  return (
    <section className="extreme-workspace" id="extreme-alerts" aria-label="85 and 15 extreme alerts">
      <header className="extreme-header">
        <div className="extreme-title">
          <span className="extreme-title-icon"><BellRing size={18} /></span>
          <div>
            <h2>85 / 15 Extreme Scanner</h2>
            <span>RSI(1) + short MACD histogram + moving-average confirmation</span>
          </div>
        </div>
        <div className="extreme-actions">
          <span className="alert-preferences">
            <Volume2 size={13} className={soundEnabled ? "active" : ""} />
            <span className={voiceEnabled ? "active" : ""}>Voice</span>
          </span>
          <button className="icon-text" type="button" disabled={busy} onClick={onRun}>
            <Radio size={15} className={busy ? "pulse" : ""} />
            Scan now
          </button>
        </div>
      </header>

      <div className="extreme-status">
        <span className={scan?.source === "mt5" ? "live-dot" : ""} />
        <strong>{scan?.source === "mt5" ? "Live MT5 data" : "Waiting for verified MT5 data"}</strong>
        <span>{scan ? `${scan.scanned_symbols} of ${scan.available_symbols} instruments scanned` : "The first scan is starting"}</span>
        <b>Alert at 85.00 or 15.00</b>
      </div>

      <div className="extreme-notification-controls">
        <div className="extreme-notification-title">
          <BellRing size={15} />
          <div>
            <strong>Threshold notifications</strong>
            <span>Rows stay visible; these toggles control sound and voice delivery.</span>
          </div>
        </div>
        <div className="extreme-notification-options">
          <label className="extreme-notification-toggle upper">
            <input
              type="checkbox"
              checked={upper85NotificationsEnabled}
              onChange={(event) => onUpper85NotificationsToggle(event.target.checked)}
            />
            <span className="toggle-track"><span /></span>
            <span>85.00 <b>Sell watch</b></span>
          </label>
          <label className="extreme-notification-toggle lower">
            <input
              type="checkbox"
              checked={lower15NotificationsEnabled}
              onChange={(event) => onLower15NotificationsToggle(event.target.checked)}
            />
            <span className="toggle-track"><span /></span>
            <span>15.00 <b>Buy watch</b></span>
          </label>
        </div>
      </div>

      <div className="extreme-levels">
        <div className="level-card upper"><strong>85.00</strong><span>Upper extreme</span><small>SELL watch</small></div>
        <div className="level-card middle"><strong>50.00</strong><span>Neutral center</span><small>Confirmation required</small></div>
        <div className="level-card lower"><strong>15.00</strong><span>Lower extreme</span><small>BUY watch</small></div>
        <div className="extreme-method"><ShieldAlert size={15} /><span>Alerts fire on entry into a zone, then respect a five-minute cooldown. They never place orders.</span></div>
      </div>

      {alerts.length ? (
        <div className="new-alerts">
          <div className="extreme-subheading"><strong>New threshold alerts</strong><span>{alerts.length} just detected</span></div>
          {alerts.map((alert) => (
            <AlertRow key={alert.id} alert={alert} expanded={expanded === alert.id} onToggle={() => setExpanded(expanded === alert.id ? null : alert.id)} />
          ))}
        </div>
      ) : (
        <div className="no-new-alerts">
          <Clock3 size={15} />
          <span>No new 85.00 / 15.00 threshold crossing in the latest scan.</span>
          <b>{scan?.recent_alerts.length ?? 0} recent alerts retained</b>
        </div>
      )}

      <div className="extreme-readings">
        <div className="extreme-subheading"><strong>Current extreme readings</strong><span>{extremes.length ? "Closest active zones first" : "No active extremes"}</span></div>
        {extremes.length ? extremes.map((reading) => <ReadingRow key={reading.symbol} reading={reading} />) : <div className="extreme-empty">The scanner will show instruments here when the merged score reaches either configured level.</div>}
      </div>

      <footer className="extreme-footnote">{scan?.disclaimer ?? "The composite is decision support. No indicator combination guarantees a reversal or a profitable trade."}</footer>
    </section>
  );
}

function AlertRow({ alert, expanded, onToggle }: { alert: ExtremeAlert; expanded: boolean; onToggle: () => void }) {
  const upper = alert.level === "upper_85";
  return (
    <article className={`extreme-alert-row ${upper ? "upper" : "lower"}`}>
      <div className="extreme-alert-main">
        <span className="alert-symbol"><strong>{alert.symbol}</strong><small>{upper ? "85.00 reached" : "15.00 reached"}</small></span>
        <span className="alert-score"><strong>{alert.score.toFixed(2)}</strong><small>composite score</small></span>
        <span className="alert-factors"><b>RSI {alert.rsi1.toFixed(2)}</b><b>MACD {alert.macd >= 0 ? "+" : ""}{alert.macd.toFixed(5)}</b><b>MA {alert.ema_fast >= alert.ema_slow ? "up" : "down"}</b></span>
        <span className={`alert-recommendation ${upper ? "sell" : "buy"}`}>
          <b>{upper ? "SELL watch" : "BUY watch"}</b>
          <small>{alert.recommendation}</small>
        </span>
        <button className="icon-button compact-icon" type="button" title="Show alert reasoning" aria-label={`Show ${alert.symbol} alert reasoning`} onClick={onToggle}><ChevronDown size={14} /></button>
      </div>
      {expanded && <div className="alert-reasoning"><span>{dateTime(alert.triggered_at)}</span>{alert.reasons.map((reason) => <p key={reason}>{reason}</p>)}</div>}
    </article>
  );
}

function ReadingRow({ reading }: { reading: ExtremeReading }) {
  const levelClass = reading.level === "upper_85" ? "upper" : reading.level === "lower_15" ? "lower" : "neutral";
  return (
    <div className="extreme-reading-row">
      <strong>{reading.symbol}</strong>
      <span className={`reading-level ${levelClass}`}>{reading.score.toFixed(2)}</span>
      <span className="reading-bar"><i style={{ width: `${reading.score}%` }} /></span>
      <span>RSI(1) {reading.rsi1.toFixed(0)}</span>
      <span>MACD {reading.macd >= 0 ? "+" : ""}{reading.macd.toFixed(4)}</span>
      <span className={`reading-recommendation ${levelClass === "upper" ? "sell" : "buy"}`}>
        <b>{levelClass === "upper" ? "SELL watch" : "BUY watch"}</b>
        <small>{reading.recommendation}</small>
      </span>
    </div>
  );
}

function dateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value));
}
