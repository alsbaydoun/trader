import { ExternalLink, GripHorizontal, GripVertical, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type KeyboardEvent,
  type PointerEvent
} from "react";
import type { Candle, Signal } from "../types";
import { getOverlayLines, type ActiveIndicator, type IndicatorLine } from "../lib/indicators";
import { IndicatorStack } from "./IndicatorStack";

interface ChartPanelProps {
  symbol: string;
  timeframe: string;
  candles: Candle[];
  signal?: Signal;
  indicators: ActiveIndicator[];
  focused: boolean;
  onFocus: (symbol: string) => void;
  onIndicatorsChange: (indicators: ActiveIndicator[]) => void;
  onMove: (source: string, target: string) => void;
  onMoveByOffset: (symbol: string, offset: number) => void;
  height?: number;
  onResize: (symbol: string, height: number) => void;
}

interface HoveredCandle {
  index: number;
  tooltipX: number;
  tooltipY: number;
}

const MIN_VISIBLE_CANDLES = 30;
const DEFAULT_VISIBLE_CANDLES = 120;
const ZOOM_STEP = 30;
export const CHART_HEIGHT_MIN = 560;
export const CHART_HEIGHT_MAX = 960;
const CHART_HEIGHT_DEFAULT = 560;

export function ChartPanel({
  symbol,
  timeframe,
  candles,
  signal,
  indicators,
  focused,
  onFocus,
  onIndicatorsChange,
  onMove,
  onMoveByOffset,
  height,
  onResize
}: ChartPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const resizeRef = useRef<{ startY: number; startHeight: number } | null>(null);
  const moveRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    lastTarget: string | null;
    active: boolean;
  } | null>(null);
  const [visibleCount, setVisibleCount] = useState(DEFAULT_VISIBLE_CANDLES);
  const [hovered, setHovered] = useState<HoveredCandle | null>(null);
  const [isResizing, setIsResizing] = useState(false);
  const [isMoving, setIsMoving] = useState(false);
  const visibleCandles = useMemo(
    () => candles.slice(-Math.min(visibleCount, candles.length)),
    [candles, visibleCount]
  );
  const overlayLines = useMemo(() => getOverlayLines(visibleCandles, indicators), [indicators, visibleCandles]);
  const hoveredCandle = hovered ? visibleCandles[hovered.index] : undefined;
  const source = candles.at(-1)?.source ?? "demo";

  useEffect(() => {
    setHovered(null);
  }, [timeframe, visibleCount]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || visibleCandles.length === 0) return;
    const render = () => {
      const rect = canvas.getBoundingClientRect();
      const scale = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(rect.width * scale));
      canvas.height = Math.max(1, Math.floor(rect.height * scale));
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      drawChart(ctx, rect.width, rect.height, visibleCandles, signal, hovered?.index, overlayLines);
    };
    render();
    const observer = new ResizeObserver(render);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [hovered?.index, overlayLines, signal, visibleCandles]);

  function zoomIn() {
    setVisibleCount((current) => Math.max(MIN_VISIBLE_CANDLES, current - ZOOM_STEP));
  }

  function zoomOut() {
    setVisibleCount((current) => Math.min(candles.length || current, current + ZOOM_STEP));
  }

  function resetZoom() {
    setVisibleCount(Math.min(DEFAULT_VISIBLE_CANDLES, candles.length || DEFAULT_VISIBLE_CANDLES));
  }

  function currentHeight() {
    return height ?? CHART_HEIGHT_DEFAULT;
  }

  function setChartHeight(nextHeight: number) {
    onResize(symbol, Math.max(CHART_HEIGHT_MIN, Math.min(CHART_HEIGHT_MAX, nextHeight)));
  }

  function startResize(event: PointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    resizeRef.current = { startY: event.clientY, startHeight: currentHeight() };
    setIsResizing(true);
  }

  function moveResize(event: PointerEvent<HTMLButtonElement>) {
    const resize = resizeRef.current;
    if (!resize) return;
    setChartHeight(resize.startHeight + event.clientY - resize.startY);
  }

  function finishResize(event: PointerEvent<HTMLButtonElement>) {
    if (!resizeRef.current) return;
    event.stopPropagation();
    resizeRef.current = null;
    setIsResizing(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function handleResizeKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const current = currentHeight();
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      setChartHeight(current + 20);
    } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      setChartHeight(current - 20);
    } else if (event.key === "Home") {
      event.preventDefault();
      setChartHeight(CHART_HEIGHT_MIN);
    } else if (event.key === "End") {
      event.preventDefault();
      setChartHeight(CHART_HEIGHT_MAX);
    }
  }

  function startMove(event: PointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    moveRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      lastTarget: symbol,
      active: false
    };
  }

  function moveChart(event: PointerEvent<HTMLButtonElement>) {
    const move = moveRef.current;
    if (!move || move.pointerId !== event.pointerId) return;
    if (!move.active) {
      const distance = Math.hypot(event.clientX - move.startX, event.clientY - move.startY);
      if (distance < 8) return;
      move.active = true;
      setIsMoving(true);
    }
    const target = document
      .elementFromPoint(event.clientX, event.clientY)
      ?.closest<HTMLElement>("[data-chart-symbol]")
      ?.dataset.chartSymbol;
    if (!target || target === symbol || target === move.lastTarget) return;
    move.lastTarget = target;
    onMove(symbol, target);
  }

  function finishMove(event: PointerEvent<HTMLButtonElement>) {
    const move = moveRef.current;
    if (!move || move.pointerId !== event.pointerId) return;
    event.stopPropagation();
    moveRef.current = null;
    setIsMoving(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function startNativeMove(event: DragEvent<HTMLButtonElement>) {
    event.stopPropagation();
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/trader-symbol", symbol);
    setIsMoving(true);
  }

  function finishNativeMove() {
    setIsMoving(false);
  }

  function allowNativeDrop(event: DragEvent<HTMLElement>) {
    if (!event.dataTransfer.types.includes("text/trader-symbol")) return;
    if (event.currentTarget.getAttribute("data-chart-symbol") === symbol) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }

  function dropChart(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    const source = event.dataTransfer.getData("text/trader-symbol");
    if (source && source !== symbol) onMove(source, symbol);
    setIsMoving(false);
  }

  function handleMoveKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      onMoveByOffset(symbol, -1);
    } else if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      onMoveByOffset(symbol, 1);
    }
  }

  function inspectCandle(clientX: number, clientY: number) {
    const canvas = canvasRef.current;
    if (!canvas || visibleCandles.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const paddingLeft = 14;
    const paddingRight = 54;
    const chartWidth = Math.max(1, rect.width - paddingLeft - paddingRight);
    const x = Math.min(chartWidth, Math.max(0, clientX - rect.left - paddingLeft));
    const index = Math.min(
      visibleCandles.length - 1,
      Math.max(0, Math.round((x / chartWidth) * (visibleCandles.length - 1)))
    );
    const pointerX = clientX - rect.left;
    setHovered({
      index,
      tooltipX: pointerX > rect.width * 0.58 ? pointerX - 202 : pointerX + 12,
      tooltipY: Math.max(8, Math.min(clientY - rect.top - 40, rect.height - 188))
    });
  }

  function openPopout() {
    const popout = window.open("", `${symbol}-chart`, "width=1180,height=760");
    if (!popout) return;
    popout.document.write(`
      <html>
        <head>
          <title>${symbol} ${timeframe}</title>
          <style>
            body { margin:0; background:#101418; color:#eef2f5; font-family:Inter,Arial,sans-serif; }
            .bar { height:48px; display:flex; align-items:center; justify-content:space-between; padding:0 16px; border-bottom:1px solid #26313a; }
            canvas { width:100vw; height:calc(100vh - 48px); display:block; }
          </style>
        </head>
        <body>
          <div class="bar"><strong>${symbol}</strong><span>${timeframe} ${signal?.direction ?? "hold"}</span></div>
          <canvas id="chart"></canvas>
        </body>
      </html>
    `);
    const canvas = popout.document.getElementById("chart") as HTMLCanvasElement | null;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const render = () => {
      const width = popout.innerWidth;
      const height = popout.innerHeight - 48;
      const scale = popout.devicePixelRatio || 1;
      canvas.width = width * scale;
      canvas.height = height * scale;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      if (!ctx) return;
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      drawChart(ctx, width, height, visibleCandles, signal, undefined, overlayLines);
    };
    render();
    popout.addEventListener("resize", render);
  }

  const hoveredIndex = hovered?.index;
  const candleEnd = hoveredCandle && hoveredIndex !== undefined
    ? new Date(
        visibleCandles[hoveredIndex + 1]?.ts ??
          new Date(new Date(hoveredCandle.ts).getTime() + timeframeMilliseconds(timeframe)).toISOString()
      )
    : undefined;

  return (
    <section
      className={`chart-panel ${focused ? "is-focused" : ""} ${isResizing ? "is-resizing" : ""} ${isMoving ? "is-moving" : ""}`}
      data-chart-symbol={symbol}
      style={height ? { height: `${height}px` } : undefined}
      onClick={() => onFocus(symbol)}
      onDragOver={allowNativeDrop}
      onDrop={dropChart}
    >
      <header className="panel-title">
        <div className="chart-heading">
          <button
            className="chart-drag-handle"
            type="button"
            draggable
            aria-label={`Move ${symbol} chart`}
            title="Drag to move chart"
            onPointerDown={startMove}
            onPointerMove={moveChart}
            onPointerUp={finishMove}
            onPointerCancel={finishMove}
            onDragStart={startNativeMove}
            onDragEnd={finishNativeMove}
            onKeyDown={handleMoveKeyDown}
            onLostPointerCapture={() => {
              moveRef.current = null;
              setIsMoving(false);
            }}
            onClick={(event) => event.stopPropagation()}
          >
            <GripVertical size={15} aria-hidden="true" />
          </button>
          <div>
            <strong>{symbol}</strong>
            <span>{timeframe} <b className={`data-source ${source}`}>{source === "mt5" ? "MT5" : "Demo"}</b></span>
          </div>
        </div>
        <div className="chart-actions">
          <div className={`direction ${signal?.direction ?? "hold"}`}>{signal?.direction ?? "hold"}</div>
          <button className="icon-button" type="button" onClick={zoomIn} aria-label={`Zoom in ${symbol}`}>
            <ZoomIn size={15} />
          </button>
          <button className="icon-button" type="button" onClick={zoomOut} aria-label={`Zoom out ${symbol}`}>
            <ZoomOut size={15} />
          </button>
          <button className="icon-button" type="button" onClick={resetZoom} aria-label={`Reset ${symbol} zoom`}>
            <RotateCcw size={14} />
          </button>
          <button className="icon-button" type="button" onClick={openPopout} aria-label={`Open ${symbol} chart`}>
            <ExternalLink size={15} />
          </button>
        </div>
      </header>
      <div
        className="chart-canvas-wrap"
        onPointerMove={(event) => inspectCandle(event.clientX, event.clientY)}
        onPointerDown={(event) => inspectCandle(event.clientX, event.clientY)}
        onPointerLeave={() => setHovered(null)}
        onWheel={(event) => {
          event.preventDefault();
          if (event.deltaY < 0) zoomIn();
          else zoomOut();
        }}
      >
        <canvas ref={canvasRef} className="price-chart" />
        {hoveredCandle && candleEnd && hovered && (
          <div className="candle-tooltip" style={{ left: hovered.tooltipX, top: hovered.tooltipY }}>
            <strong>{symbol} candle</strong>
            <span>Start <b>{formatExactTime(new Date(hoveredCandle.ts))}</b></span>
            <span>End <b>{formatExactTime(candleEnd)}</b></span>
            <div className="candle-values">
              <span>O <b>{formatPrice(hoveredCandle.open, symbol)}</b></span>
              <span>H <b>{formatPrice(hoveredCandle.high, symbol)}</b></span>
              <span>L <b>{formatPrice(hoveredCandle.low, symbol)}</b></span>
              <span>C <b>{formatPrice(hoveredCandle.close, symbol)}</b></span>
            </div>
            <small>Volume {Math.round(hoveredCandle.volume).toLocaleString()}</small>
          </div>
        )}
      </div>
      <footer className="chart-footer">
        <span>{candles.at(-1) ? formatPrice(candles.at(-1)!.close, symbol) : "--"}</span>
        <span>{visibleCandles.length} candles visible</span>
        <span>{signal ? `${Math.round(signal.confidence * 100)}% confidence` : "waiting"}</span>
      </footer>
      <IndicatorStack
        symbol={symbol}
        timeframe={timeframe}
        candles={candles}
        signal={signal}
        indicators={indicators}
        onChange={onIndicatorsChange}
      />
      <button
        className={`chart-resize-handle ${isResizing ? "active" : ""}`}
        type="button"
        role="separator"
        aria-label={`Resize ${symbol} chart`}
        aria-orientation="horizontal"
        aria-valuemin={CHART_HEIGHT_MIN}
        aria-valuemax={CHART_HEIGHT_MAX}
        aria-valuenow={currentHeight()}
        title="Drag to resize chart"
        onPointerDown={startResize}
        onPointerMove={moveResize}
        onPointerUp={finishResize}
        onPointerCancel={finishResize}
        onLostPointerCapture={() => {
          resizeRef.current = null;
          setIsResizing(false);
        }}
        onKeyDown={handleResizeKeyDown}
        onClick={(event) => event.stopPropagation()}
      >
        <GripHorizontal size={15} aria-hidden="true" />
      </button>
    </section>
  );
}

function drawChart(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  candles: Candle[],
  signal?: Signal,
  hoveredIndex?: number,
  overlayLines: IndicatorLine[] = []
) {
  ctx.clearRect(0, 0, width, height);
  const padding = { top: 18, right: 54, bottom: 30, left: 14 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const highs = candles.map((candle) => candle.high);
  const lows = candles.map((candle) => candle.low);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const range = max - min || 1;
  const xStep = chartWidth / Math.max(1, candles.length - 1);

  ctx.fillStyle = "#101418";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "#27333d";
  ctx.lineWidth = 1;
  for (let index = 0; index < 5; index += 1) {
    const y = padding.top + (chartHeight / 4) * index;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
  }

  candles.forEach((candle, index) => {
    const x = padding.left + index * xStep;
    const openY = priceToY(candle.open, min, range, padding.top, chartHeight);
    const closeY = priceToY(candle.close, min, range, padding.top, chartHeight);
    const highY = priceToY(candle.high, min, range, padding.top, chartHeight);
    const lowY = priceToY(candle.low, min, range, padding.top, chartHeight);
    const up = candle.close >= candle.open;
    ctx.strokeStyle = up ? "#2ed8a3" : "#ff647c";
    ctx.fillStyle = ctx.strokeStyle;
    ctx.beginPath();
    ctx.moveTo(x, highY);
    ctx.lineTo(x, lowY);
    ctx.stroke();
    const bodyHeight = Math.max(2, Math.abs(closeY - openY));
    const candleWidth = Math.max(2, Math.min(9, xStep * 0.56));
    ctx.fillRect(x - candleWidth / 2, Math.min(openY, closeY), candleWidth, bodyHeight);
  });

  overlayLines.forEach((line) => drawIndicatorLine(ctx, line, padding.left, chartWidth, padding.top, chartHeight, min, range, xStep));

  if (hoveredIndex !== undefined) {
    const x = padding.left + hoveredIndex * xStep;
    ctx.strokeStyle = "#91a0ac";
    ctx.setLineDash([3, 4]);
    ctx.beginPath();
    ctx.moveTo(x, padding.top);
    ctx.lineTo(x, height - padding.bottom);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  if (signal?.stop_loss) drawLevel(ctx, signal.stop_loss, min, range, padding.top, chartHeight, width, "#ff647c", "SL");
  if (signal?.take_profit) drawLevel(ctx, signal.take_profit, min, range, padding.top, chartHeight, width, "#2ed8a3", "TP");
  if (signal) drawLevel(ctx, signal.entry, min, range, padding.top, chartHeight, width, "#e7c766", "ENTRY");

  ctx.fillStyle = "#8a98a6";
  ctx.font = "11px Inter, Arial";
  ctx.fillText(max.toFixed(2), width - 48, padding.top + 4);
  ctx.fillText(min.toFixed(2), width - 48, height - padding.bottom);
  drawTimeAxis(ctx, candles, padding.left, chartWidth, height - 8);
}

function drawIndicatorLine(
  ctx: CanvasRenderingContext2D,
  line: IndicatorLine,
  left: number,
  width: number,
  top: number,
  height: number,
  min: number,
  range: number,
  xStep: number
) {
  ctx.save();
  ctx.strokeStyle = line.color;
  ctx.lineWidth = 1.35;
  if (line.dashed) ctx.setLineDash([4, 4]);
  ctx.beginPath();
  let drawing = false;
  line.values.forEach((value, index) => {
    if (!Number.isFinite(value)) {
      drawing = false;
      return;
    }
    const x = left + index * xStep;
    const y = priceToY(value, min, range, top, height);
    if (!drawing) {
      ctx.moveTo(x, y);
      drawing = true;
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = line.color;
  ctx.font = "9px Inter, Arial";
  const last = [...line.values].reverse().find((value) => Number.isFinite(value));
  if (last !== undefined) ctx.fillText(line.label, left + width - 44, priceToY(last, min, range, top, height) - 3);
  ctx.restore();
}

function drawTimeAxis(
  ctx: CanvasRenderingContext2D,
  candles: Candle[],
  left: number,
  width: number,
  y: number
) {
  if (!candles.length) return;
  const points = [0, Math.floor((candles.length - 1) / 2), candles.length - 1];
  ctx.fillStyle = "#6f7e8a";
  ctx.font = "10px Inter, Arial";
  points.forEach((index, position) => {
    const label = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(
      new Date(candles[index].ts)
    );
    const x = left + (width * index) / Math.max(1, candles.length - 1);
    ctx.textAlign = position === 0 ? "left" : position === 2 ? "right" : "center";
    ctx.fillText(label, x, y);
  });
  ctx.textAlign = "left";
}

function priceToY(price: number, min: number, range: number, top: number, height: number) {
  return top + height - ((price - min) / range) * height;
}

function drawLevel(
  ctx: CanvasRenderingContext2D,
  price: number,
  min: number,
  range: number,
  top: number,
  height: number,
  width: number,
  color: string,
  label: string
) {
  const y = priceToY(price, min, range, top, height);
  ctx.strokeStyle = color;
  ctx.setLineDash([5, 5]);
  ctx.beginPath();
  ctx.moveTo(14, y);
  ctx.lineTo(width - 58, y);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = color;
  ctx.font = "10px Inter, Arial";
  ctx.fillText(label, width - 52, y - 4);
}

function timeframeMilliseconds(timeframe: string): number {
  const amount = Number.parseInt(timeframe, 10) || 1;
  if (timeframe.endsWith("d")) return amount * 24 * 60 * 60 * 1000;
  if (timeframe.endsWith("h")) return amount * 60 * 60 * 1000;
  return amount * 60 * 1000;
}

function formatExactTime(value: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short"
  }).format(value);
}

function formatPrice(value: number, symbol: string): string {
  const digits = symbol.includes("BTC") || value >= 10000 ? 1 : value < 10 ? 4 : 2;
  return value.toFixed(digits);
}
