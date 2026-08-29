/**
 * useChartStore — Zustand store for chart-related state.
 *
 * Replaces the scattered useState calls in TradingViewLayout with a
 * single, testable store. Only chart state lives here; UI state
 * (fullscreen, alert panel, etc.) stays in component-local state.
 *
 * Pattern: one store per domain (chart, watchlist, analysis, etc.)
 * as recommended in docs/specs/2026-08-25-tradingview-quality-gui-master-plan.md.
 */

import { create } from "zustand";
import type { KlineData, MacdData, RsiData, BollingerData } from "./types";
import type { Timeframe, DrawingTool, CrosshairInfo } from "../components/tradingview/types";

interface ChartState {
  // ── Ticker ──────────────────────────────────────────────────────
  ticker: string;
  stockName: string | undefined;

  // ── Timeframe ───────────────────────────────────────────────────
  timeframe: Timeframe;

  // ── Data ────────────────────────────────────────────────────────
  kline: KlineData | null;
  macd: MacdData | null;
  rsi: RsiData | null;
  bollinger: BollingerData | null;

  // ── UI state ────────────────────────────────────────────────────
  crosshairInfo: CrosshairInfo | null;
  activeTool: DrawingTool;
  activeOverlays: string[];
  isLoading: boolean;
  loadError: string | null;

  // ── Replay ──────────────────────────────────────────────────────
  replayDate: string | null;
  isPlaying: boolean;

  // ── Multi-chart ─────────────────────────────────────────────────
  isMultiChart: boolean;
}

interface ChartActions {
  // ── Setters ─────────────────────────────────────────────────────
  setTicker: (ticker: string, name?: string) => void;
  setTimeframe: (tf: Timeframe) => void;
  setKline: (kline: KlineData | null) => void;
  setMacd: (macd: MacdData | null) => void;
  setRsi: (rsi: RsiData | null) => void;
  setBollinger: (bollinger: BollingerData | null) => void;
  setCrosshairInfo: (info: CrosshairInfo | null) => void;
  setActiveTool: (tool: DrawingTool) => void;
  toggleOverlay: (key: string) => void;
  setLoading: (loading: boolean) => void;
  setLoadError: (error: string | null) => void;
  setReplayDate: (date: string | null) => void;
  setIsPlaying: (playing: boolean) => void;
  setMultiChart: (multi: boolean) => void;

  // ── Bulk updates ────────────────────────────────────────────────
  loadChartData: (data: {
    kline?: KlineData | null;
    macd?: MacdData | null;
    rsi?: RsiData | null;
    bollinger?: BollingerData | null;
  }) => void;

  reset: () => void;
}

const INITIAL_STATE: ChartState = {
  ticker: "AAPL",
  stockName: undefined,
  timeframe: "1D",
  kline: null,
  macd: null,
  rsi: null,
  bollinger: null,
  crosshairInfo: null,
  activeTool: "crosshair",
  activeOverlays: ["ma5", "ma10", "ma20", "ma50"],
  isLoading: false,
  loadError: null,
  replayDate: null,
  isPlaying: false,
  isMultiChart: false,
};

export const useChartStore = create<ChartState & ChartActions>((set) => ({
  ...INITIAL_STATE,

  setTicker: (ticker, name) => set({ ticker, stockName: name }),
  setTimeframe: (timeframe) => set({ timeframe }),
  setKline: (kline) => set({ kline }),
  setMacd: (macd) => set({ macd }),
  setRsi: (rsi) => set({ rsi }),
  setBollinger: (bollinger) => set({ bollinger }),
  setCrosshairInfo: (crosshairInfo) => set({ crosshairInfo }),
  setActiveTool: (activeTool) => set({ activeTool }),
  toggleOverlay: (key) =>
    set((s) => ({
      activeOverlays: s.activeOverlays.includes(key)
        ? s.activeOverlays.filter((k) => k !== key)
        : [...s.activeOverlays, key],
    })),
  setLoading: (isLoading) => set({ isLoading }),
  setLoadError: (loadError) => set({ loadError }),
  setReplayDate: (replayDate) => set({ replayDate }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setMultiChart: (isMultiChart) => set({ isMultiChart }),

  loadChartData: (data) =>
    set((s) => ({
      kline: data.kline ?? s.kline,
      macd: data.macd ?? s.macd,
      rsi: data.rsi ?? s.rsi,
      bollinger: data.bollinger ?? s.bollinger,
    })),

  reset: () => set(INITIAL_STATE),
}));
