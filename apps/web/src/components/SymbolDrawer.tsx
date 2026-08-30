import { useMemo, useState } from "react";
import { GripVertical, Plus, Radar, RefreshCw, Search, X } from "lucide-react";
import type { MarketOpportunity, MarketScan, MarketSymbol } from "../types";

interface SymbolDrawerProps {
  open: boolean;
  selectedSymbols: string[];
  catalog: MarketSymbol[];
  marketScan?: MarketScan;
  scanning: boolean;
  onClose: () => void;
  onAdd: (symbol: string) => void;
  onRemove: (symbol: string) => void;
  onMove: (source: string, target: string) => void;
  onScan: () => void;
}

export function SymbolDrawer({
  open,
  selectedSymbols,
  catalog,
  marketScan,
  scanning,
  onClose,
  onAdd,
  onRemove,
  onMove,
  onScan
}: SymbolDrawerProps) {
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"ranked" | "catalog">("ranked");
  const [dragged, setDragged] = useState<string | null>(null);
  const filteredCatalog = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return catalog.slice(0, 150);
    return catalog
      .filter(
        (item) =>
          item.symbol.toLowerCase().includes(normalized) ||
          item.description.toLowerCase().includes(normalized) ||
          item.category.toLowerCase().includes(normalized)
      )
      .slice(0, 150);
  }, [catalog, query]);
  const ranked = useMemo(() => {
    const opportunities = marketScan?.opportunities ?? [];
    const normalized = query.trim().toLowerCase();
    if (!normalized) return opportunities;
    return opportunities.filter(
      (item) =>
        item.symbol.toLowerCase().includes(normalized) ||
        item.description.toLowerCase().includes(normalized) ||
        item.category.toLowerCase().includes(normalized)
    );
  }, [marketScan, query]);

  return (
    <>
      <button
        className={open ? "drawer-scrim visible" : "drawer-scrim"}
        type="button"
        aria-label="Close pairs drawer"
        onClick={onClose}
      />
      <aside className={open ? "symbol-drawer open" : "symbol-drawer"} aria-hidden={!open}>
        <header className="drawer-header">
          <div>
            <strong>Markets</strong>
            <span>{catalog.length} instruments available</span>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close markets">
            <X size={17} />
          </button>
        </header>

        <section className="selected-markets" aria-label="Selected charts">
          <div className="drawer-section-title">
            <span>Chart order</span>
            <small>{selectedSymbols.length} open</small>
          </div>
          <div className="selected-market-list">
            {selectedSymbols.map((symbol) => (
              <div
                className="selected-market-row"
                draggable
                key={symbol}
                onDragStart={() => {
                  setDragged(symbol);
                }}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => {
                  if (dragged && dragged !== symbol) onMove(dragged, symbol);
                  setDragged(null);
                }}
              >
                <GripVertical size={15} aria-hidden="true" />
                <strong>{symbol}</strong>
                <button
                  className="icon-button compact-icon"
                  type="button"
                  onClick={() => onRemove(symbol)}
                  aria-label={`Remove ${symbol}`}
                  disabled={selectedSymbols.length === 1}
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </section>

        <div className="market-tools">
          <label className="market-search">
            <Search size={15} />
            <span className="sr-only">Search markets</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search symbol or market"
            />
          </label>
          <button className="icon-button" type="button" onClick={onScan} aria-label="Scan all markets">
            <RefreshCw size={15} className={scanning ? "spin" : ""} />
          </button>
        </div>

        <div className="segmented drawer-tabs">
          <button
            type="button"
            className={view === "ranked" ? "active" : ""}
            onClick={() => setView("ranked")}
          >
            <Radar size={14} /> Ranked
          </button>
          <button
            type="button"
            className={view === "catalog" ? "active" : ""}
            onClick={() => setView("catalog")}
          >
            All pairs
          </button>
        </div>

        {view === "ranked" ? (
          <RankedMarkets
            items={ranked}
            selected={selectedSymbols}
            scan={marketScan}
            onAdd={onAdd}
          />
        ) : (
          <Catalog items={filteredCatalog} selected={selectedSymbols} onAdd={onAdd} />
        )}
      </aside>
    </>
  );
}

function RankedMarkets({
  items,
  selected,
  scan,
  onAdd
}: {
  items: MarketOpportunity[];
  selected: string[];
  scan?: MarketScan;
  onAdd: (symbol: string) => void;
}) {
  return (
    <section className="drawer-results">
      <div className="scan-summary">
        <span>{scan ? `${scan.scanned_symbols}/${scan.available_symbols} scanned` : "Waiting for scan"}</span>
        <span>{scan?.timeframe ?? "1m"}</span>
      </div>
      {scan && <p className="scan-disclaimer">{scan.disclaimer}</p>}
      {items.map((item) => (
        <div className="opportunity-row" key={item.symbol}>
          <span className="opportunity-rank">{item.rank}</span>
          <div
            className="opportunity-name"
            title={`${item.recommendation}: ${item.reasons.map((reason) => reason.message).join(" ")}`}
          >
            <strong>{item.symbol}</strong>
            <span>
              {item.market_active
                ? `${item.recommendation} - ${item.reasons[0]?.message ?? item.description}`
                : "Market inactive"}
            </span>
          </div>
          <div className={`opportunity-score ${item.direction}`}>
            <strong>{Math.round(item.opportunity_score)}</strong>
            <span>{item.direction}</span>
          </div>
          <button
            className="icon-button compact-icon"
            type="button"
            onClick={() => onAdd(item.symbol)}
            aria-label={`Add ${item.symbol} chart`}
            disabled={selected.includes(item.symbol)}
          >
            <Plus size={14} />
          </button>
        </div>
      ))}
      {!items.length && <p className="drawer-empty">No ranked opportunities are available yet.</p>}
    </section>
  );
}

function Catalog({
  items,
  selected,
  onAdd
}: {
  items: MarketSymbol[];
  selected: string[];
  onAdd: (symbol: string) => void;
}) {
  return (
    <section className="drawer-results">
      {items.map((item) => (
        <div className="catalog-row" key={item.symbol}>
          <div>
            <strong>{item.symbol}</strong>
            <span>{item.description}</span>
          </div>
          <span className="market-category">{item.category}</span>
          <button
            className="icon-button compact-icon"
            type="button"
            onClick={() => onAdd(item.symbol)}
            aria-label={`Add ${item.symbol} chart`}
            disabled={selected.includes(item.symbol)}
          >
            <Plus size={14} />
          </button>
        </div>
      ))}
      {!items.length && <p className="drawer-empty">No markets match this search.</p>}
    </section>
  );
}
