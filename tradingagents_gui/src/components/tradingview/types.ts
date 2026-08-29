/** TradingView chart-specific types */

import type { KlineData, MacdData, RsiData, BollingerData, FundFlowData } from "../../lib/types";

// ── Timeframes ──────────────────────────────────────────────────────────────

/** Bar interval for chart data. Minute intervals hit the backend minute path;
 *  day-based timeframes map to a calendar-day window via TIMEFRAME_DAYS. */
export type Timeframe = "1m" | "5m" | "15m" | "30m" | "60m" | "1D" | "1W" | "1M" | "3M" | "1Y" | "ALL";

export const MINUTE_TIMEFRAMES: Timeframe[] = ["1m", "5m", "15m", "30m", "60m"];

export function isMinuteTimeframe(tf: Timeframe): boolean {
  return (MINUTE_TIMEFRAMES as string[]).includes(tf);
}

export const TIMEFRAME_DAYS: Record<Timeframe, number> = {
  "1m": 1,
  "5m": 7,
  "15m": 30,
  "30m": 60,
  "60m": 365,
  "1D": 90,
  "1W": 180,
  "1M": 365,
  "3M": 730,
  "1Y": 1825,
  "ALL": 3650,
};

// ── Drawing tools ───────────────────────────────────────────────────────────

export type DrawingTool =
  | "crosshair"
  | "trendline"
  | "horizontal"
  | "rectangle"
  | "fibonacci";

// ── Watchlist ───────────────────────────────────────────────────────────────

export interface WatchlistItem {
  ticker: string;
  name?: string;
  lastPrice?: number;
  change?: number;
  changePercent?: number;
}

/** A named watchlist group; the first group is the default ("自选股"). */
export interface WatchlistGroup {
  id: string;
  name: string;
  items: WatchlistItem[];
  collapsed?: boolean;
}

// ── Chart data (transformed for lightweight-charts) ─────────────────────────

export interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface VolumeData {
  time: string;
  value: number;
  color: string;
}

export interface OverlayData {
  time: string;
  value: number | null;
}

// ── Crosshair info ──────────────────────────────────────────────────────────

export interface CrosshairInfo {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  change: number;
  changePercent: number;
}

// ── Drawing primitives ──────────────────────────────────────────────────────

export interface DrawingPrimitive {
  id: string;
  type: DrawingTool;
  points: { time: string; price: number }[];
  color?: string;
  lineWidth?: number;
  lineStyle?: number;
}

// ── Component props ─────────────────────────────────────────────────────────

export interface TradingViewLayoutProps {
  kline: KlineData | null;
  macd?: MacdData | null;
  rsi?: RsiData | null;
  bollinger?: BollingerData | null;
  fundFlow?: FundFlowData | null;
  ticker: string;
  name?: string;
  onBack?: () => void;
  onAnalyze?: () => void;
}
