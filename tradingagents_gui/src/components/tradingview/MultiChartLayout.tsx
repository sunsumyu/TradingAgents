/**
 * MultiChartLayout — 1×1 / 1×2 / 2×2 grid of independent chart panes.
 *
 * Each pane loads its own chart data via /api/chart-data and renders a
 * TradingViewChart with sub-indicators. Crosshair time-axis is synced
 * across all panes via a shared context.
 */

import { useState, useCallback, createContext, useRef, useEffect } from "react";
import { LayoutGrid, Rows2, Square } from "lucide-react";
import { api } from "../../lib/api";
import type { KlineData } from "../../lib/types";
import type { CrosshairInfo, Timeframe } from "./types";
import { TIMEFRAME_DAYS, isMinuteTimeframe } from "./types";
import TradingViewChart from "./TradingViewChart";
import TimeframeSelector from "./TimeframeSelector";

// ── Crosshair sync context ─────────────────────────────────────────────────

interface CrosshairSync {
  /** Bar index to sync to (null = no sync). */
  barIndex: number | null;
  /** Date string of the synced bar. */
  date: string | null;
}

const CrosshairSyncContext = createContext<CrosshairSync>({ barIndex: null, date: null });
const CrosshairSyncDispatch = createContext<(info: CrosshairSync) => void>(() => {});

// ── Layout types ────────────────────────────────────────────────────────────

type LayoutMode = "1x1" | "1x2" | "2x2";

const LAYOUT_OPTIONS: { mode: LayoutMode; label: string; icon: typeof Square }[] = [
  { mode: "1x1", label: "1×1", icon: Square },
  { mode: "1x2", label: "1×2", icon: Rows2 },
  { mode: "2x2", label: "2×2", icon: LayoutGrid },
];

function gridClass(mode: LayoutMode): string {
  switch (mode) {
    case "1x1": return "grid-cols-1 grid-rows-1";
    case "1x2": return "grid-cols-2 grid-rows-1";
    case "2x2": return "grid-cols-2 grid-rows-2";
  }
}

// ── Default tickers for each pane position ──────────────────────────────────

const DEFAULT_TICKERS = ["600519", "000858", "000001", "300750"];

// ── Single chart pane ───────────────────────────────────────────────────────

interface PaneProps {
  initialTicker: string;
  timeframe: Timeframe;
  onCrosshairBroadcast: (info: CrosshairSync) => void;
}

function ChartPane({ initialTicker, timeframe, onCrosshairBroadcast }: PaneProps) {
  const [ticker, setTicker] = useState(initialTicker);
  const [kline, setKline] = useState<KlineData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState(initialTicker);
  const abortRef = useRef<AbortController | null>(null);

  // Load data on mount and when ticker/timeframe changes
  useEffect(() => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setLoading(true);
    setError(null);

    const days = TIMEFRAME_DAYS[timeframe];
    const interval = isMinuteTimeframe(timeframe) ? timeframe : null;

    api.getChartData(ticker, new Date().toISOString().slice(0, 10), days, ctrl.signal, interval)
      .then((data) => {
        if (!ctrl.signal.aborted) {
          setKline(data.kline ?? null);
        }
      })
      .catch((err) => {
        if (err.name !== "AbortError" && !ctrl.signal.aborted) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });

    return () => ctrl.abort();
  }, [ticker, timeframe]);

  const handleTickerSubmit = useCallback(() => {
    const t = inputValue.trim().toUpperCase();
    if (t && t !== ticker) setTicker(t);
  }, [inputValue, ticker]);

  const handleCrosshairMove = useCallback((info: CrosshairInfo | null) => {
    if (info && info.time) {
      onCrosshairBroadcast({ barIndex: null, date: info.time });
    }
  }, [onCrosshairBroadcast]);

  return (
    <div className="relative border border-line rounded bg-bg-primary overflow-hidden flex flex-col">
      {/* Pane header */}
      <div className="h-7 shrink-0 flex items-center px-2 bg-bg-secondary/60 border-b border-line gap-1.5">
        <input
          type="text"
          className="w-16 text-[11px] bg-transparent border border-line rounded px-1 py-0.5 text-accent font-mono outline-none focus:border-accent"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleTickerSubmit()}
          onBlur={handleTickerSubmit}
        />
        {loading && (
          <span className="w-2 h-2 border border-accent/50 border-t-accent rounded-full animate-spin" />
        )}
        {error && (
          <span className="text-[10px] text-down truncate flex-1">{error}</span>
        )}
      </div>

      {/* Chart area */}
      <div className="flex-1 min-h-0">
        {kline ? (
          <TradingViewChart
            data={kline}
            activeOverlays={["ma5", "ma10", "ma20"]}
            onCrosshairMove={handleCrosshairMove}
          />
        ) : (
          <div className="h-full flex items-center justify-center text-text-muted text-[11px]">
            {loading ? "加载中..." : "无数据"}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main layout ─────────────────────────────────────────────────────────────

interface Props {
  initialTicker?: string;
}

export default function MultiChartLayout({ initialTicker = "600519" }: Props) {
  const [layout, setLayout] = useState<LayoutMode>("2x2");
  const [timeframe, setTimeframe] = useState<Timeframe>("1D");
  const [crosshairSync, setCrosshairSync] = useState<CrosshairSync>({ barIndex: null, date: null });

  const paneCount = layout === "1x1" ? 1 : layout === "1x2" ? 2 : 4;

  const handleCrosshairBroadcast = useCallback((info: CrosshairSync) => {
    setCrosshairSync(info);
  }, []);

  // Persist layout preference
  useEffect(() => {
    try {
      const saved = localStorage.getItem("tradingagents_multi_layout");
      if (saved && ["1x1", "1x2", "2x2"].includes(saved)) {
        setLayout(saved as LayoutMode);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("tradingagents_multi_layout", layout);
    } catch { /* ignore */ }
  }, [layout]);

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="h-9 shrink-0 flex items-center px-3 border-b border-line bg-bg-secondary/60 gap-3">
        <span className="text-[12px] font-medium text-text-primary">多图表布局</span>

        <div className="flex items-center gap-0.5 ml-2">
          {LAYOUT_OPTIONS.map(({ mode, label, icon: Icon }) => (
            <button
              key={mode}
              className={`px-2 py-1 text-[11px] rounded flex items-center gap-1 transition-colors ${
                layout === mode
                  ? "bg-accent/15 text-accent border border-accent/40"
                  : "text-text-secondary hover:bg-bg-hover border border-transparent"
              }`}
              onClick={() => setLayout(mode)}
            >
              <Icon size={12} />
              {label}
            </button>
          ))}
        </div>

        <div className="ml-auto">
          <TimeframeSelector
            current={timeframe}
            onChange={setTimeframe}
          />
        </div>
      </div>

      {/* Grid */}
      <CrosshairSyncContext.Provider value={crosshairSync}>
        <CrosshairSyncDispatch.Provider value={handleCrosshairBroadcast}>
          <div className={`flex-1 grid gap-1 p-1 ${gridClass(layout)}`}>
            {Array.from({ length: paneCount }, (_, i) => (
              <ChartPane
                key={i}
                initialTicker={DEFAULT_TICKERS[i] ?? initialTicker}
                timeframe={timeframe}
                onCrosshairBroadcast={handleCrosshairBroadcast}
              />
            ))}
          </div>
        </CrosshairSyncDispatch.Provider>
      </CrosshairSyncContext.Provider>
    </div>
  );
}
