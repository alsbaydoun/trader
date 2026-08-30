import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CalendarClock,
  ChevronDown,
  ExternalLink,
  Globe2,
  Newspaper,
  TrendingDown,
  TrendingUp
} from "lucide-react";
import type { MarketEvent, MarketImpact, NewsStatus } from "../types";

interface NewsAnalysisPanelProps {
  activeSymbol: string;
  events: MarketEvent[];
  status?: NewsStatus;
}

export function NewsAnalysisPanel({ activeSymbol, events, status }: NewsAnalysisPanelProps) {
  const [view, setView] = useState<"global" | "symbol">("symbol");
  const [expanded, setExpanded] = useState(false);
  const visibleEvents = useMemo(
    () =>
      view === "global"
        ? events.filter((event) => event.scope === "global")
        : events.filter((event) => event.impacts.some((impact) => impact.symbol === activeSymbol)),
    [activeSymbol, events, view]
  );

  return (
    <section className={`rail-block news-analysis ${expanded ? "expanded" : "collapsed"}`}>
      <button
        aria-controls="news-analysis-content"
        aria-expanded={expanded}
        className="news-toggle"
        type="button"
        onClick={() => setExpanded((open) => !open)}
      >
        <span className="news-toggle-title">
          <Newspaper size={17} />
          <span>
            <strong>News Analysis</strong>
            <small>AI context</small>
          </span>
        </span>
        <span className="news-summary-count">
          {events.length} {events.length === 1 ? "event" : "events"}
        </span>
        <span className={`news-state ${status?.state ?? "config_required"}`}>
          {status?.state === "live"
            ? "Live calendar"
            : status?.state === "stale"
              ? "Stale"
              : "Source needed"}
        </span>
        <ChevronDown className="news-toggle-chevron" size={16} />
      </button>

      {expanded && (
        <div className="news-analysis-content" id="news-analysis-content">
          <div className="segmented news-tabs" aria-label="News analysis scope">
            <button
              className={view === "global" ? "active" : ""}
              type="button"
              onClick={() => setView("global")}
            >
              <Globe2 size={14} />
              Global
            </button>
            <button
              className={view === "symbol" ? "active" : ""}
              type="button"
              onClick={() => setView("symbol")}
            >
              {activeSymbol}
            </button>
          </div>

          {status && (
            <div className={`news-source ${status.state}`}>
              <strong>{status.provider}</strong>
              <p>{status.message}</p>
              <div className="coverage-row">
                <span className={status.calendar_connected ? "covered" : "missing"}>Calendar</span>
                <span className={status.headlines_connected ? "covered" : "missing"}>Headlines</span>
              </div>
            </div>
          )}

          {visibleEvents.length ? (
            <div className="news-event-list">
              {visibleEvents.map((event) => (
                <NewsEvent
                  activeSymbol={activeSymbol}
                  event={event}
                  global={view === "global"}
                  key={event.id}
                />
              ))}
            </div>
          ) : (
            <div className="news-empty">
              <AlertTriangle size={16} />
              <div>
                <strong>No verified events available</strong>
                <p>
                  {view === "global"
                    ? "No global event analysis is available from the connected sources."
                    : `No verified news analysis is available for ${activeSymbol}.`}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function NewsEvent({
  activeSymbol,
  event,
  global
}: {
  activeSymbol: string;
  event: MarketEvent;
  global: boolean;
}) {
  const impact = event.impacts.find((item) => item.symbol === activeSymbol);
  return (
    <article className={`news-event severity-${event.severity}`}>
      <div className="news-event-meta">
        <span>{event.category}</span>
        <span className={`severity ${event.severity}`}>{event.severity}</span>
        <time dateTime={event.event_time}>
          <CalendarClock size={12} />
          {formatEventTime(event.event_time)}
        </time>
      </div>
      <h3>{event.title}</h3>
      <p className="analysis-copy">{global ? event.analysis : impact?.thesis ?? event.analysis}</p>

      {hasValues(event) && (
        <div className="event-values">
          <Value label="Actual" value={event.actual} />
          <Value label="Forecast" value={event.forecast} />
          <Value label="Previous" value={event.previous} />
        </div>
      )}

      {global ? <GlobalImpacts event={event} /> : impact && <SymbolImpact impact={impact} />}

      <details className="news-details">
        <summary>Reasoning and risk</summary>
        {global ? (
          <ul>
            {event.why_it_matters.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : impact ? (
          <>
            <div className="causal-chain">
              {impact.causal_chain.map((step) => (
                <span key={step}>{step}</span>
              ))}
            </div>
            <p><strong>Bullish if:</strong> {impact.bullish_trigger}</p>
            <p><strong>Bearish if:</strong> {impact.bearish_trigger}</p>
            <p><strong>Invalid if:</strong> {impact.invalidation}</p>
          </>
        ) : null}
        <p className="risk-window"><AlertTriangle size={13} />{event.risk_window}</p>
      </details>

      {event.source_url && (
        <a className="news-source-link" href={event.source_url} target="_blank" rel="noreferrer">
          Source <ExternalLink size={12} />
        </a>
      )}
    </article>
  );
}

function GlobalImpacts({ event }: { event: MarketEvent }) {
  const material = event.impacts.filter((impact) => impact.direction !== "neutral").slice(0, 7);
  return (
    <div className="impact-strip" aria-label="Expected instrument impact">
      {material.map((impact) => (
        <span className={impact.direction} key={impact.symbol}>
          {impact.symbol}
          <DirectionIcon direction={impact.direction} />
        </span>
      ))}
    </div>
  );
}

function SymbolImpact({ impact }: { impact: MarketImpact }) {
  return (
    <div className={`symbol-impact ${impact.direction}`}>
      <span>{impact.direction}</span>
      <strong>{Math.round(impact.confidence * 100)}% confidence</strong>
      <small>{impact.horizon}</small>
    </div>
  );
}

function DirectionIcon({ direction }: { direction: MarketImpact["direction"] }) {
  if (direction === "bullish") return <TrendingUp size={12} />;
  if (direction === "bearish") return <TrendingDown size={12} />;
  return <span aria-hidden="true">?</span>;
}

function Value({ label, value }: { label: string; value: number | null }) {
  return (
    <span>
      {label}
      <strong>{value ?? "--"}</strong>
    </span>
  );
}

function hasValues(event: MarketEvent): boolean {
  return event.actual !== null || event.forecast !== null || event.previous !== null;
}

function formatEventTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
