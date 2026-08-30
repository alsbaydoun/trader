import { Activity, BarChart3, BrainCircuit, Gauge, Layers3, Plus, Settings2, Sparkles, TrendingUp, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { Candle, Signal } from "../types";
import {
  buildAIIndicatorReading,
  buildIndicatorReadings,
  createIndicator,
  INDICATOR_CATALOG,
  INDICATOR_PRESETS,
  indicatorDefinition,
  indicatorKey,
  type ActiveIndicator,
  type IndicatorKind,
  type IndicatorReading
} from "../lib/indicators";

interface IndicatorStackProps {
  symbol: string;
  timeframe: string;
  candles: Candle[];
  signal?: Signal;
  indicators: ActiveIndicator[];
  onChange: (indicators: ActiveIndicator[]) => void;
}

export function IndicatorStack({ symbol, timeframe, candles, signal, indicators, onChange }: IndicatorStackProps) {
  const [selectedKind, setSelectedKind] = useState<IndicatorKind | "">("");
  const [selectedPreset, setSelectedPreset] = useState("");
  const readings = useMemo(() => buildIndicatorReadings(candles, signal, indicators), [candles, indicators, signal]);
  const aiReading = useMemo(() => buildAIIndicatorReading(readings), [readings]);
  const overlayCount = indicators.filter((indicator) => indicatorDefinition(indicator.kind).overlay).length;

  function addSelectedIndicator() {
    if (!selectedKind) return;
    const next = createIndicator(selectedKind);
    if (indicators.some((indicator) => indicatorKey(indicator) === indicatorKey(next))) return;
    onChange([...indicators, next]);
    setSelectedKind("");
  }

  function removeIndicator(target: ActiveIndicator) {
    onChange(indicators.filter((indicator) => indicatorKey(indicator) !== indicatorKey(target)));
  }

  function updateIndicator(target: ActiveIndicator, update: Partial<ActiveIndicator>) {
    const next = { ...target, ...update };
    if (indicators.some((indicator) => indicator !== target && indicatorKey(indicator) === indicatorKey(next))) return;
    onChange(indicators.map((indicator) => indicator === target ? next : indicator));
  }

  function loadPreset() {
    if (!selectedPreset) return;
    onChange(INDICATOR_PRESETS[selectedPreset].map((indicator) => ({ ...indicator })));
    setSelectedPreset("");
  }

  return (
    <details className="indicator-stack" open>
      <summary>
        <span className="indicator-stack-title">
          <Layers3 size={15} />
          <strong>Indicators & AI reading</strong>
        </span>
        <span className="indicator-stack-summary">
          {indicators.length} active · {overlayCount} on chart · {symbol} {timeframe}
        </span>
      </summary>

      <div className="indicator-toolbar">
        <div className="indicator-toolbar-field">
          <label htmlFor={`indicator-add-${symbol}`}>Add indicator</label>
          <select
            id={`indicator-add-${symbol}`}
            value={selectedKind}
            onChange={(event) => setSelectedKind(event.target.value as IndicatorKind | "")}
          >
            <option value="">Choose an indicator</option>
            {INDICATOR_CATALOG.map((definition) => (
              <option value={definition.kind} key={definition.kind}>
                {definition.label} · {definition.group}
              </option>
            ))}
          </select>
        </div>
        <button
          className="icon-button indicator-add-button"
          type="button"
          title="Add selected indicator"
          aria-label="Add selected indicator"
          disabled={!selectedKind}
          onClick={addSelectedIndicator}
        >
          <Plus size={15} />
        </button>
        <div className="indicator-toolbar-field preset-field">
          <label htmlFor={`indicator-preset-${symbol}`}>Preset</label>
          <select
            id={`indicator-preset-${symbol}`}
            value={selectedPreset}
            onChange={(event) => setSelectedPreset(event.target.value)}
          >
            <option value="">Load a set</option>
            {Object.keys(INDICATOR_PRESETS).map((preset) => <option value={preset} key={preset}>{preset}</option>)}
          </select>
        </div>
        <button
          className="text-button indicator-load-button"
          type="button"
          disabled={!selectedPreset}
          onClick={loadPreset}
        >
          Load
        </button>
      </div>

      <div className="indicator-chip-row" aria-label={`${symbol} active indicators`}>
        {indicators.length ? indicators.map((indicator) => (
          <span className={`indicator-chip ${indicatorDefinition(indicator.kind).overlay ? "overlay" : "pane"}`} key={indicatorKey(indicator)}>
            <span>{indicatorDefinition(indicator.kind).label}</span>
            <small>{indicatorParameters(indicator)}</small>
            <button
              type="button"
              title={`Remove ${indicatorDefinition(indicator.kind).label}`}
              aria-label={`Remove ${indicatorDefinition(indicator.kind).label}`}
              onClick={() => removeIndicator(indicator)}
            >
              <X size={12} />
            </button>
          </span>
        )) : <span className="muted">No indicators selected. Add one to start the AI reading.</span>}
      </div>

      <div className={`indicator-ai-reading ${aiReading.tone}`}>
        <div className="indicator-ai-heading">
          <span className="indicator-ai-title"><Sparkles size={14} /><strong>AI-assisted reading</strong></span>
          <span className={`indicator-ai-bias ${aiReading.tone}`}>
            <BrainCircuit size={13} /> {aiReading.direction}
          </span>
        </div>
        <p>{aiReading.summary}</p>
        <div className="indicator-ai-meta">
          <span>Agreement {aiReading.alignment}%</span>
          <span>Closed-candle context</span>
        </div>
        <div className="indicator-ai-reasons">
          {aiReading.reasons.map((reason) => <span key={reason}>{reason}</span>)}
        </div>
        <div className="indicator-ai-watch"><strong>Watch:</strong> {aiReading.watch}</div>
      </div>

      <div className="indicator-readings">
        {readings.map((reading) => (
          <IndicatorReadingCard
            key={`${reading.name}-${reading.parameters}`}
            reading={reading}
            indicator={indicators.find((item) => indicatorKey(item) === reading.key)}
            onChange={updateIndicator}
          />
        ))}
      </div>
      <div className="indicator-disclaimer">
        <Activity size={13} />
        <span>AI summarizes selected technical readings. It does not predict certainty or guarantee a profitable trade.</span>
      </div>
    </details>
  );
}

function IndicatorReadingCard({
  reading,
  indicator,
  onChange
}: {
  reading: IndicatorReading;
  indicator?: ActiveIndicator;
  onChange: (target: ActiveIndicator, update: Partial<ActiveIndicator>) => void;
}) {
  return (
    <article className="indicator-reading">
      <div className="indicator-reading-heading">
        <span className="indicator-reading-name">
          {indicatorIcon(reading.name)}
          <strong>{reading.name}</strong>
        </span>
        <span className="indicator-reading-tools">
          <span>{reading.parameters}</span>
          {indicator && <IndicatorSettings indicator={indicator} onChange={(update) => onChange(indicator, update)} />}
        </span>
      </div>
      {reading.gauge !== undefined && (
        <div className="indicator-gauge" aria-hidden="true">
          <i style={{ width: `${Math.max(2, Math.min(100, reading.gauge))}%` }} />
          {(reading.name === "RSI" || reading.name === "Stochastic") && <><b className="gauge-line upper" /><b className="gauge-line lower" /></>}
        </div>
      )}
      <div className="indicator-reading-result">
        <strong className={reading.tone}>{reading.value}</strong>
        <span className={reading.tone}>{reading.status}</span>
      </div>
      <p>{reading.detail}</p>
    </article>
  );
}

function IndicatorSettings({ indicator, onChange }: { indicator: ActiveIndicator; onChange: (update: Partial<ActiveIndicator>) => void }) {
  return (
    <details className="indicator-settings">
      <summary title="Adjust indicator parameters" aria-label="Adjust indicator parameters"><Settings2 size={12} /></summary>
      <div className="indicator-settings-popover">
        {indicator.kind === "macd" ? (
          <>
            <ParameterInput label="Fast" value={indicator.fast ?? 12} onChange={(fast) => onChange({ fast })} />
            <ParameterInput label="Slow" value={indicator.slow ?? 26} onChange={(slow) => onChange({ slow })} />
            <ParameterInput label="Signal" value={indicator.signal ?? 9} onChange={(signal) => onChange({ signal })} />
          </>
        ) : indicator.kind === "ichimoku" ? (
          <>
            <ParameterInput label="Conv" value={indicator.conversion ?? 9} onChange={(conversion) => onChange({ conversion })} />
            <ParameterInput label="Base" value={indicator.base ?? 26} onChange={(base) => onChange({ base })} />
            <ParameterInput label="Span" value={indicator.span ?? 52} onChange={(span) => onChange({ span })} />
          </>
        ) : (
          <ParameterInput label="Period" value={indicator.period ?? 14} onChange={(period) => onChange({ period })} />
        )}
        {indicator.kind === "bollinger" && (
          <ParameterInput label="Std dev" step={0.1} value={indicator.deviation ?? 2} onChange={(deviation) => onChange({ deviation })} />
        )}
        {indicator.kind === "stochastic" && (
          <ParameterInput label="Smooth" value={indicator.signal ?? 3} onChange={(signal) => onChange({ signal })} />
        )}
      </div>
    </details>
  );
}

function ParameterInput({ label, value, step = 1, onChange }: { label: string; value: number; step?: number; onChange: (value: number) => void }) {
  return (
    <label>
      <span>{label}</span>
      <input
        type="number"
        min={step < 1 ? 0.5 : 2}
        max={250}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value) || 2)}
      />
    </label>
  );
}

function indicatorParameters(indicator: ActiveIndicator): string {
  if (indicator.kind === "macd") return `${indicator.fast ?? 12}/${indicator.slow ?? 26}/${indicator.signal ?? 9}`;
  if (indicator.kind === "ichimoku") return `${indicator.conversion ?? 9}/${indicator.base ?? 26}/${indicator.span ?? 52}`;
  if (indicator.kind === "bollinger") return `${indicator.period ?? 20}/${indicator.deviation ?? 2}`;
  if (indicator.kind === "vwap") return "session";
  return `${indicator.period ?? 14}`;
}

function indicatorIcon(name: string) {
  if (name === "RSI" || name === "Stochastic") return <Gauge size={13} />;
  if (name === "MACD") return <BarChart3 size={13} />;
  if (name === "ATR" || name === "Bollinger Bands") return <Activity size={13} />;
  return <TrendingUp size={13} />;
}
