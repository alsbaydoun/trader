import type { Candle, Signal } from "../types";

export type IndicatorKind =
  | "ema"
  | "sma"
  | "bollinger"
  | "vwap"
  | "ichimoku"
  | "rsi"
  | "macd"
  | "stochastic"
  | "adx"
  | "atr"
  | "structure";

export interface ActiveIndicator {
  kind: IndicatorKind;
  period?: number;
  fast?: number;
  slow?: number;
  signal?: number;
  deviation?: number;
  conversion?: number;
  base?: number;
  span?: number;
}

export interface IndicatorDefinition {
  kind: IndicatorKind;
  label: string;
  group: "Overlay" | "Momentum" | "Volatility" | "Trend" | "Structure";
  description: string;
  overlay: boolean;
  defaultConfig: ActiveIndicator;
}

export interface IndicatorLine {
  label: string;
  color: string;
  values: number[];
  dashed?: boolean;
}

export interface IndicatorReading {
  key?: string;
  name: string;
  parameters: string;
  value: string;
  status: string;
  tone: "positive" | "negative" | "neutral" | "warning";
  gauge?: number;
  detail: string;
  bias: number;
}

export interface AIIndicatorReading {
  direction: "BUY BIAS" | "SELL BIAS" | "WAIT";
  tone: "positive" | "negative" | "neutral";
  alignment: number;
  summary: string;
  reasons: string[];
  watch: string;
}

export const INDICATOR_CATALOG: IndicatorDefinition[] = [
  {
    kind: "ema",
    label: "EMA",
    group: "Overlay",
    description: "Tracks trend direction with more weight on recent candles.",
    overlay: true,
    defaultConfig: { kind: "ema", period: 20 }
  },
  {
    kind: "sma",
    label: "SMA",
    group: "Overlay",
    description: "Smooths price over a fixed number of candles.",
    overlay: true,
    defaultConfig: { kind: "sma", period: 50 }
  },
  {
    kind: "bollinger",
    label: "Bollinger Bands",
    group: "Volatility",
    description: "Shows a moving average with volatility bands around it.",
    overlay: true,
    defaultConfig: { kind: "bollinger", period: 20, deviation: 2 }
  },
  {
    kind: "vwap",
    label: "VWAP",
    group: "Overlay",
    description: "Compares price with the volume-weighted average for each session.",
    overlay: true,
    defaultConfig: { kind: "vwap" }
  },
  {
    kind: "ichimoku",
    label: "Ichimoku Cloud",
    group: "Trend",
    description: "Maps trend, support, resistance, and momentum structure.",
    overlay: true,
    defaultConfig: { kind: "ichimoku", conversion: 9, base: 26, span: 52 }
  },
  {
    kind: "rsi",
    label: "RSI",
    group: "Momentum",
    description: "Measures momentum and highlights stretched conditions.",
    overlay: false,
    defaultConfig: { kind: "rsi", period: 14 }
  },
  {
    kind: "macd",
    label: "MACD",
    group: "Momentum",
    description: "Compares moving averages to show momentum and crossovers.",
    overlay: false,
    defaultConfig: { kind: "macd", fast: 12, slow: 26, signal: 9 }
  },
  {
    kind: "stochastic",
    label: "Stochastic",
    group: "Momentum",
    description: "Compares the close with its recent range for momentum timing.",
    overlay: false,
    defaultConfig: { kind: "stochastic", period: 14, signal: 3 }
  },
  {
    kind: "adx",
    label: "ADX + DI",
    group: "Trend",
    description: "Measures trend strength and directional pressure.",
    overlay: false,
    defaultConfig: { kind: "adx", period: 14 }
  },
  {
    kind: "atr",
    label: "ATR",
    group: "Volatility",
    description: "Measures the current trading range for risk and stop context.",
    overlay: false,
    defaultConfig: { kind: "atr", period: 14 }
  },
  {
    kind: "structure",
    label: "Price Structure",
    group: "Structure",
    description: "Checks recent highs, lows, breakouts, and candle direction.",
    overlay: false,
    defaultConfig: { kind: "structure", period: 20 }
  }
];

export const DEFAULT_INDICATORS: ActiveIndicator[] = [
  { kind: "ema", period: 20 },
  { kind: "ema", period: 50 },
  { kind: "rsi", period: 14 },
  { kind: "macd", fast: 12, slow: 26, signal: 9 },
  { kind: "atr", period: 14 }
];

export const INDICATOR_PRESETS: Record<string, ActiveIndicator[]> = {
  "Trend follow": [
    { kind: "ema", period: 20 },
    { kind: "ema", period: 50 },
    { kind: "ichimoku", conversion: 9, base: 26, span: 52 },
    { kind: "adx", period: 14 },
    { kind: "atr", period: 14 }
  ],
  "Momentum check": [
    { kind: "rsi", period: 14 },
    { kind: "macd", fast: 12, slow: 26, signal: 9 },
    { kind: "stochastic", period: 14, signal: 3 },
    { kind: "structure", period: 20 }
  ],
  "Volatility map": [
    { kind: "bollinger", period: 20, deviation: 2 },
    { kind: "atr", period: 14 },
    { kind: "vwap" },
    { kind: "structure", period: 20 }
  ]
};

export function createIndicator(kind: IndicatorKind): ActiveIndicator {
  const definition = INDICATOR_CATALOG.find((item) => item.kind === kind);
  return definition ? { ...definition.defaultConfig } : { kind: "rsi", period: 14 };
}

export function indicatorDefinition(kind: IndicatorKind): IndicatorDefinition {
  return INDICATOR_CATALOG.find((item) => item.kind === kind) ?? INDICATOR_CATALOG[0];
}

export function indicatorKey(indicator: ActiveIndicator): string {
  return [
    indicator.kind,
    indicator.period,
    indicator.fast,
    indicator.slow,
    indicator.signal,
    indicator.deviation,
    indicator.conversion,
    indicator.base,
    indicator.span
  ].join("-");
}

export function getOverlayLines(candles: Candle[], indicators: ActiveIndicator[]): IndicatorLine[] {
  const closes = candles.map((candle) => candle.close);
  const lines: IndicatorLine[] = [];
  for (const indicator of indicators) {
    if (!indicatorDefinition(indicator.kind).overlay) continue;
    if (indicator.kind === "ema") {
      lines.push({
        label: `EMA ${indicator.period ?? 20}`,
        color: indicator.period === 50 ? "#78aef5" : "#e7c766",
        values: emaSeries(closes, safePeriod(indicator.period, 20))
      });
    } else if (indicator.kind === "sma") {
      lines.push({
        label: `SMA ${indicator.period ?? 50}`,
        color: "#b4a7ff",
        values: smaSeries(closes, safePeriod(indicator.period, 50))
      });
    } else if (indicator.kind === "bollinger") {
      const bands = bollingerSeries(closes, safePeriod(indicator.period, 20), safeDeviation(indicator.deviation));
      lines.push(
        { label: "BB upper", color: "#9b8cf2", values: bands.upper, dashed: true },
        { label: "BB middle", color: "#d9d1ff", values: bands.middle },
        { label: "BB lower", color: "#9b8cf2", values: bands.lower, dashed: true }
      );
    } else if (indicator.kind === "vwap") {
      lines.push({ label: "VWAP", color: "#ff9e64", values: vwapSeries(candles) });
    } else if (indicator.kind === "ichimoku") {
      const cloud = ichimokuSeries(
        candles,
        safePeriod(indicator.conversion, 9),
        safePeriod(indicator.base, 26),
        safePeriod(indicator.span, 52)
      );
      lines.push(
        { label: "Tenkan", color: "#64d7c4", values: cloud.conversion },
        { label: "Kijun", color: "#f49b9b", values: cloud.base },
        { label: "Cloud A", color: "#75b8dc", values: cloud.spanA, dashed: true },
        { label: "Cloud B", color: "#d995b4", values: cloud.spanB, dashed: true }
      );
    }
  }
  return lines;
}

export function buildIndicatorReadings(
  candles: Candle[],
  signal: Signal | undefined,
  indicators: ActiveIndicator[]
): IndicatorReading[] {
  if (candles.length < 3) {
    return [{
      name: "Indicator workspace",
      parameters: "loading",
      value: "--",
      status: "Waiting",
      tone: "neutral",
      detail: "Waiting for enough candle data to calculate the selected indicators.",
      bias: 0
    }];
  }

  const readings: IndicatorReading[] = indicators.map((indicator) => ({ ...buildReading(candles, indicator), key: indicatorKey(indicator) }));
  if (signal && signal.direction !== "hold") {
    readings.push({
      name: "Workstation signal",
      parameters: "scanner",
      value: signal.direction.toUpperCase(),
      status: `${Math.round(signal.confidence * 100)}% confidence`,
      tone: signal.direction === "buy" ? "positive" : "negative",
      detail: signal.reasons[0]?.message ?? "The scanner has a directional setup.",
      bias: signal.direction === "buy" ? 1 : -1
    });
  }
  return readings;
}

export function buildAIIndicatorReading(readings: IndicatorReading[]): AIIndicatorReading {
  const directional = readings.filter((reading) => reading.bias !== 0);
  const bullish = directional.filter((reading) => reading.bias > 0).reduce((sum, reading) => sum + reading.bias, 0);
  const bearish = directional.filter((reading) => reading.bias < 0).reduce((sum, reading) => sum + Math.abs(reading.bias), 0);
  const total = bullish + bearish;
  const dominant = total ? Math.max(bullish, bearish) / total : 0;
  const alignment = Math.round(dominant * 100);
  const conflicts = bullish > 0 && bearish > 0;
  const strongest = [...directional].sort((a, b) => Math.abs(b.bias) - Math.abs(a.bias)).slice(0, 3);
  const reasons = strongest.map((reading) => `${reading.name}: ${reading.status}.`);
  const warnings = readings.filter((reading) => reading.tone === "warning").map((reading) => `${reading.name}: ${reading.detail}`);

  if (!directional.length || Math.abs(bullish - bearish) < 1) {
    return {
      direction: "WAIT",
      tone: "neutral",
      alignment,
      summary: "The selected indicators do not have a clear directional agreement yet.",
      reasons: reasons.length ? reasons : ["Add more candle history or select a directional indicator."],
      watch: warnings[0] ?? "Wait for a closed candle and stronger agreement before treating this as a setup."
    };
  }

  const bullishBias = bullish > bearish;
  return {
    direction: bullishBias ? "BUY BIAS" : "SELL BIAS",
    tone: bullishBias ? "positive" : "negative",
    alignment,
    summary: conflicts
      ? `The indicators lean ${bullishBias ? "bullish" : "bearish"}, but there is disagreement. Treat this as a bias, not an entry command.`
      : `The selected indicators are aligned ${bullishBias ? "bullishly" : "bearishly"} on the latest available candle.`,
    reasons: reasons.length ? reasons : ["Directional readings are available."],
    watch: warnings[0] ?? "Confirm the next closed candle, spread, and nearby support or resistance."
  };
}

function buildReading(candles: Candle[], indicator: ActiveIndicator): IndicatorReading {
  const closes = candles.map((candle) => candle.close);
  const current = closes.at(-1) ?? 0;
  const previous = closes.at(-2) ?? current;
  const period = safePeriod(indicator.period, 14);

  if (indicator.kind === "ema" || indicator.kind === "sma") {
    const value = indicator.kind === "ema" ? lastFinite(emaSeries(closes, period)) : lastFinite(smaSeries(closes, period));
    const bias = current > value ? 1 : current < value ? -1 : 0;
    return {
      name: indicator.kind.toUpperCase(),
      parameters: `${period} candles`,
      value: formatPrice(value),
      status: bias > 0 ? "Price above average" : bias < 0 ? "Price below average" : "At average",
      tone: bias > 0 ? "positive" : bias < 0 ? "negative" : "neutral",
      detail: `${formatPrice(Math.abs(current - value))} distance from the ${indicator.kind.toUpperCase()} reference.`,
      bias
    };
  }

  if (indicator.kind === "bollinger") {
    const bands = bollingerSeries(closes, period, safeDeviation(indicator.deviation));
    const middle = lastFinite(bands.middle);
    const upper = lastFinite(bands.upper);
    const lower = lastFinite(bands.lower);
    const outside = current > upper || current < lower;
    const bias = current > middle ? 0.5 : current < middle ? -0.5 : 0;
    return {
      name: "Bollinger Bands",
      parameters: `${period} / ${safeDeviation(indicator.deviation)} SD`,
      value: outside ? current > upper ? "Above upper" : "Below lower" : "Inside bands",
      status: outside ? "Price is stretched" : current > middle ? "Upper half" : "Lower half",
      tone: outside ? "warning" : bias > 0 ? "positive" : bias < 0 ? "negative" : "neutral",
      detail: `Upper ${formatPrice(upper)} · middle ${formatPrice(middle)} · lower ${formatPrice(lower)}.`,
      bias
    };
  }

  if (indicator.kind === "vwap") {
    const value = lastFinite(vwapSeries(candles));
    const bias = current > value ? 1 : current < value ? -1 : 0;
    return {
      name: "VWAP",
      parameters: "session",
      value: formatPrice(value),
      status: bias > 0 ? "Price above VWAP" : bias < 0 ? "Price below VWAP" : "At VWAP",
      tone: bias > 0 ? "positive" : bias < 0 ? "negative" : "neutral",
      detail: "A volume-weighted reference for judging whether price is trading above or below the session mean.",
      bias
    };
  }

  if (indicator.kind === "ichimoku") {
    const cloud = ichimokuSeries(candles, safePeriod(indicator.conversion, 9), safePeriod(indicator.base, 26), safePeriod(indicator.span, 52));
    const conversion = lastFinite(cloud.conversion);
    const base = lastFinite(cloud.base);
    const spanA = lastFinite(cloud.spanA);
    const spanB = lastFinite(cloud.spanB);
    const cloudTop = Math.max(spanA, spanB);
    const cloudBottom = Math.min(spanA, spanB);
    const bias = current > cloudTop && conversion > base ? 2 : current < cloudBottom && conversion < base ? -2 : 0;
    return {
      name: "Ichimoku",
      parameters: `${indicator.conversion ?? 9}/${indicator.base ?? 26}/${indicator.span ?? 52}`,
      value: bias > 0 ? "Above cloud" : bias < 0 ? "Below cloud" : "In cloud",
      status: conversion > base ? "Conversion above base" : conversion < base ? "Conversion below base" : "Lines meeting",
      tone: bias > 0 ? "positive" : bias < 0 ? "negative" : "warning",
      detail: `Cloud ${formatPrice(cloudBottom)} – ${formatPrice(cloudTop)}.`,
      bias
    };
  }

  if (indicator.kind === "rsi") {
    const value = lastFinite(rsiSeries(closes, period));
    const bias = value >= 50 && value < 70 ? 1 : value <= 50 && value > 30 ? -1 : value <= 30 ? 0.5 : value >= 70 ? -0.5 : 0;
    const stretched = value <= 30 || value >= 70;
    return {
      name: "RSI",
      parameters: `period ${period}`,
      value: value.toFixed(2),
      status: value >= 70 ? "Overbought watch" : value <= 30 ? "Oversold watch" : value >= 50 ? "Positive momentum" : "Negative momentum",
      tone: stretched ? "warning" : bias > 0 ? "positive" : bias < 0 ? "negative" : "neutral",
      gauge: value,
      detail: stretched ? "Momentum is stretched; a reversal or continuation needs price confirmation." : "Momentum is inside the normal range.",
      bias
    };
  }

  if (indicator.kind === "macd") {
    const macd = macdSeries(closes, safePeriod(indicator.fast, 12), safePeriod(indicator.slow, 26), safePeriod(indicator.signal, 9));
    const histogram = lastFinite(macd.histogram);
    const previousHistogram = previousFinite(macd.histogram);
    const bias = histogram > 0 && histogram >= previousHistogram ? 2 : histogram < 0 && histogram <= previousHistogram ? -2 : histogram > 0 ? 1 : histogram < 0 ? -1 : 0;
    return {
      name: "MACD",
      parameters: `${indicator.fast ?? 12}/${indicator.slow ?? 26}/${indicator.signal ?? 9}`,
      value: formatCompact(histogram),
      status: bias > 0 ? "Bullish histogram" : bias < 0 ? "Bearish histogram" : "Crossing or flat",
      tone: bias > 0 ? "positive" : bias < 0 ? "negative" : "neutral",
      detail: `MACD ${formatCompact(lastFinite(macd.main))} · signal ${formatCompact(lastFinite(macd.signal))}.`,
      bias
    };
  }

  if (indicator.kind === "stochastic") {
    const stochastic = stochasticSeries(candles, period, safePeriod(indicator.signal, 3));
    const value = lastFinite(stochastic.k);
    const signalValue = lastFinite(stochastic.d);
    const bias = value > signalValue && value < 80 ? 1 : value < signalValue && value > 20 ? -1 : value <= 20 ? 0.5 : value >= 80 ? -0.5 : 0;
    return {
      name: "Stochastic",
      parameters: `${period}/${indicator.signal ?? 3}`,
      value: `${value.toFixed(1)} / ${signalValue.toFixed(1)}`,
      status: value >= 80 ? "Overbought watch" : value <= 20 ? "Oversold watch" : bias > 0 ? "%K above %D" : bias < 0 ? "%K below %D" : "Neutral",
      tone: value >= 80 || value <= 20 ? "warning" : bias > 0 ? "positive" : bias < 0 ? "negative" : "neutral",
      gauge: value,
      detail: "%K is the fast reading and %D is its smoothed signal line.",
      bias
    };
  }

  if (indicator.kind === "adx") {
    const adx = adxSeries(candles, period);
    const value = lastFinite(adx.adx);
    const plus = lastFinite(adx.plus);
    const minus = lastFinite(adx.minus);
    const bias = value >= 20 ? plus > minus ? 1.5 : plus < minus ? -1.5 : 0 : 0;
    return {
      name: "ADX + DI",
      parameters: `period ${period}`,
      value: value.toFixed(1),
      status: value < 20 ? "Weak trend" : plus > minus ? "+DI leads" : minus > plus ? "-DI leads" : "Balanced pressure",
      tone: value < 20 ? "warning" : bias > 0 ? "positive" : bias < 0 ? "negative" : "neutral",
      gauge: Math.min(100, value),
      detail: `+DI ${plus.toFixed(1)} · -DI ${minus.toFixed(1)}. ADX measures strength, not direction.`,
      bias
    };
  }

  if (indicator.kind === "atr") {
    const value = lastFinite(atrSeries(candles, period));
    const percentage = current ? (value / current) * 100 : 0;
    return {
      name: "ATR",
      parameters: `period ${period}`,
      value: formatPrice(value),
      status: percentage >= 1.8 ? "Elevated volatility" : "Normal volatility",
      tone: percentage >= 1.8 ? "warning" : "neutral",
      detail: `${percentage.toFixed(2)}% of current price; useful for stop distance and position sizing.`,
      bias: 0
    };
  }

  const lookback = safePeriod(indicator.period, 20);
  const highs = candles.slice(-lookback - 1, -1).map((candle) => candle.high);
  const lows = candles.slice(-lookback - 1, -1).map((candle) => candle.low);
  const high = highs.length ? Math.max(...highs) : current;
  const low = lows.length ? Math.min(...lows) : current;
  const bias = current > high ? 2 : current < low ? -2 : previous > current ? -0.25 : previous < current ? 0.25 : 0;
  return {
    name: "Price Structure",
    parameters: `${lookback} candles`,
    value: current > high ? "Breakout up" : current < low ? "Breakdown" : "Inside range",
    status: current >= previous ? "Latest candle rising" : "Latest candle falling",
    tone: current > high ? "positive" : current < low ? "negative" : "neutral",
    detail: `Range ${formatPrice(low)} – ${formatPrice(high)}.`,
    bias
  };
}

function safePeriod(value: number | undefined, fallback: number): number {
  return Math.max(2, Math.min(250, Math.round(value ?? fallback)));
}

function safeDeviation(value: number | undefined): number {
  return Math.max(0.5, Math.min(5, value ?? 2));
}

function emaSeries(values: number[], period: number): number[] {
  if (!values.length) return [];
  const result = values.map(() => Number.NaN);
  if (values.length < period) {
    result[values.length - 1] = values.reduce((sum, value) => sum + value, 0) / values.length;
    return result;
  }
  const start = values.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
  result[period - 1] = start;
  const multiplier = 2 / (period + 1);
  for (let index = period; index < values.length; index += 1) {
    result[index] = (values[index] - result[index - 1]) * multiplier + result[index - 1];
  }
  return result;
}

function smaSeries(values: number[], period: number): number[] {
  return values.map((_, index) => {
    if (index < period - 1) return Number.NaN;
    return values.slice(index - period + 1, index + 1).reduce((sum, value) => sum + value, 0) / period;
  });
}

function bollingerSeries(values: number[], period: number, deviation: number) {
  const middle = smaSeries(values, period);
  const upper = values.map((_, index) => {
    if (index < period - 1 || !Number.isFinite(middle[index])) return Number.NaN;
    const window = values.slice(index - period + 1, index + 1);
    const variance = window.reduce((sum, value) => sum + (value - middle[index]) ** 2, 0) / period;
    return middle[index] + Math.sqrt(variance) * deviation;
  });
  const lower = upper.map((value, index) => Number.isFinite(value) && Number.isFinite(middle[index]) ? middle[index] * 2 - value : Number.NaN);
  return { middle, upper, lower };
}

function vwapSeries(candles: Candle[]): number[] {
  let totalVolume = 0;
  let totalValue = 0;
  let session = "";
  return candles.map((candle) => {
    const candleSession = candle.ts.slice(0, 10);
    if (candleSession !== session) {
      session = candleSession;
      totalVolume = 0;
      totalValue = 0;
    }
    const volume = Math.max(1, candle.volume);
    totalVolume += volume;
    totalValue += ((candle.high + candle.low + candle.close) / 3) * volume;
    return totalValue / totalVolume;
  });
}

function ichimokuSeries(candles: Candle[], conversionPeriod: number, basePeriod: number, spanPeriod: number) {
  const conversion = candles.map((_, index) => midpoint(candles, index, conversionPeriod));
  const base = candles.map((_, index) => midpoint(candles, index, basePeriod));
  const spanA = conversion.map((value, index) => Number.isFinite(value) && Number.isFinite(base[index]) ? (value + base[index]) / 2 : Number.NaN);
  const spanB = candles.map((_, index) => midpoint(candles, index, spanPeriod));
  return { conversion, base, spanA, spanB };
}

function midpoint(candles: Candle[], index: number, period: number): number {
  if (index < period - 1) return Number.NaN;
  const window = candles.slice(index - period + 1, index + 1);
  return (Math.max(...window.map((candle) => candle.high)) + Math.min(...window.map((candle) => candle.low))) / 2;
}

function rsiSeries(values: number[], period: number): number[] {
  const result = values.map(() => Number.NaN);
  if (values.length <= period) return result;
  let gains = 0;
  let losses = 0;
  for (let index = 1; index <= period; index += 1) {
    const change = values[index] - values[index - 1];
    gains += Math.max(0, change);
    losses += Math.max(0, -change);
  }
  result[period] = rsiFromAverages(gains / period, losses / period);
  for (let index = period + 1; index < values.length; index += 1) {
    const change = values[index] - values[index - 1];
    gains = (gains * (period - 1) + Math.max(0, change)) / period;
    losses = (losses * (period - 1) + Math.max(0, -change)) / period;
    result[index] = rsiFromAverages(gains, losses);
  }
  return result;
}

function rsiFromAverages(gains: number, losses: number): number {
  if (losses === 0) return gains === 0 ? 50 : 100;
  return 100 - 100 / (1 + gains / losses);
}

function macdSeries(values: number[], fastPeriod: number, slowPeriod: number, signalPeriod: number) {
  const fast = emaSeries(values, fastPeriod);
  const slow = emaSeries(values, slowPeriod);
  const main = values.map((_, index) => Number.isFinite(fast[index]) && Number.isFinite(slow[index]) ? fast[index] - slow[index] : Number.NaN);
  const signal = emaSeries(main.map((value) => Number.isFinite(value) ? value : 0), signalPeriod).map((value, index) => Number.isFinite(main[index]) ? value : Number.NaN);
  const histogram = main.map((value, index) => Number.isFinite(value) && Number.isFinite(signal[index]) ? value - signal[index] : Number.NaN);
  return { main, signal, histogram };
}

function stochasticSeries(candles: Candle[], period: number, signalPeriod: number) {
  const k = candles.map((_, index) => {
    if (index < period - 1) return Number.NaN;
    const window = candles.slice(index - period + 1, index + 1);
    const high = Math.max(...window.map((candle) => candle.high));
    const low = Math.min(...window.map((candle) => candle.low));
    return high === low ? 50 : ((candles[index].close - low) / (high - low)) * 100;
  });
  const d = smaSeries(k.map((value) => Number.isFinite(value) ? value : 50), signalPeriod).map((value, index) => Number.isFinite(k[index]) ? value : Number.NaN);
  return { k, d };
}

function atrSeries(candles: Candle[], period: number): number[] {
  const trueRanges = candles.map((candle, index) => {
    if (index === 0) return candle.high - candle.low;
    const previousClose = candles[index - 1].close;
    return Math.max(candle.high - candle.low, Math.abs(candle.high - previousClose), Math.abs(candle.low - previousClose));
  });
  return smaSeries(trueRanges, period);
}

function adxSeries(candles: Candle[], period: number) {
  const adx = candles.map(() => Number.NaN);
  const plus = candles.map(() => Number.NaN);
  const minus = candles.map(() => Number.NaN);
  for (let index = period; index < candles.length; index += 1) {
    const window = candles.slice(index - period + 1, index + 1);
    let tr = 0;
    let plusMove = 0;
    let minusMove = 0;
    for (let cursor = 1; cursor < window.length; cursor += 1) {
      const current = window[cursor];
      const previous = window[cursor - 1];
      tr += Math.max(current.high - current.low, Math.abs(current.high - previous.close), Math.abs(current.low - previous.close));
      const up = current.high - previous.high;
      const down = previous.low - current.low;
      if (up > down && up > 0) plusMove += up;
      if (down > up && down > 0) minusMove += down;
    }
    if (tr === 0) continue;
    const plusValue = (plusMove / tr) * 100;
    const minusValue = (minusMove / tr) * 100;
    const dx = plusValue + minusValue === 0 ? 0 : (Math.abs(plusValue - minusValue) / (plusValue + minusValue)) * 100;
    plus[index] = plusValue;
    minus[index] = minusValue;
    adx[index] = dx;
  }
  return { adx, plus, minus };
}

function lastFinite(values: number[]): number {
  for (let index = values.length - 1; index >= 0; index -= 1) {
    if (Number.isFinite(values[index])) return values[index];
  }
  return 0;
}

function previousFinite(values: number[]): number {
  let found = false;
  for (let index = values.length - 1; index >= 0; index -= 1) {
    if (!Number.isFinite(values[index])) continue;
    if (found) return values[index];
    found = true;
  }
  return 0;
}

function formatCompact(value: number): string {
  if (!Number.isFinite(value)) return "--";
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(2)}k`;
  if (Math.abs(value) < 0.01) return value.toFixed(5);
  return value.toFixed(3);
}

function formatPrice(value: number): string {
  if (!Number.isFinite(value)) return "--";
  if (Math.abs(value) >= 10000) return value.toFixed(1);
  if (Math.abs(value) < 10) return value.toFixed(4);
  return value.toFixed(2);
}
