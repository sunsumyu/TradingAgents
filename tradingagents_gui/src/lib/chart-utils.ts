/**
 * Shared indicator configuration and helpers for K-line charts.
 *
 * Single source of truth for overlay indicator definitions (MA/EMA),
 * used by both the report-page KlineChart and the TradingView-style
 * main chart (IndicatorBar / TradingViewChart).
 */

import type { KlineData } from "./types";

// ── Overlay indicator config ────────────────────────────────────────────────

export type IndicatorKey = "MA5" | "MA10" | "MA20" | "MA50" | "EMA12" | "EMA26";

export interface IndicatorConfig {
  key: IndicatorKey;
  field: keyof KlineData;
  color: string;
}

export const OVERLAY_INDICATORS: IndicatorConfig[] = [
  { key: "MA5", field: "ma5", color: "#F7B731" },
  { key: "MA10", field: "ma10", color: "#2962FF" },
  { key: "MA20", field: "ma20", color: "#9B59B6" },
  { key: "MA50", field: "ma50", color: "#26A69A" },
  { key: "EMA12", field: "ema12", color: "#E040FB" },
  { key: "EMA26", field: "ema26", color: "#00BCD4" },
];

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Latest value of an indicator series, formatted to 2 decimals ("—" when absent). */
export function getLatestIndicatorValue(data: KlineData, field: keyof KlineData): string {
  const arr = data[field] as (number | null)[] | undefined;
  if (!arr || arr.length === 0) return "—";
  const v = arr[arr.length - 1];
  return v != null ? v.toFixed(2) : "—";
}

/**
 * Build ECharts line series for the given active indicators.
 * Indicators without data are silently skipped.
 */
export function buildOverlaySeries(data: KlineData, visible: Set<string>) {
  return OVERLAY_INDICATORS
    .filter(({ key }) => visible.has(key))
    .filter(({ field }) => {
      const arr = data[field] as (number | null)[] | undefined;
      return arr && arr.length > 0;
    })
    .map(({ key, field, color }) => ({
      name: key,
      type: "line" as const,
      data: data[field] as (number | null)[],
      smooth: true,
      lineStyle: { width: 1.2, color },
      symbol: "none",
      z: 5,
    }));
}

// ── Adjustable indicator parameters (persisted) ─────────────────────────────

export interface MaParams {
  ma5: number;
  ma10: number;
  ma20: number;
  ma50: number;
}

export interface MacdParams {
  fast: number;
  slow: number;
  signal: number;
}

export interface IndicatorParams {
  ma: MaParams;
  macd: MacdParams;
  rsiPeriod: number;
}

export const DEFAULT_INDICATOR_PARAMS: IndicatorParams = {
  ma: { ma5: 5, ma10: 10, ma20: 20, ma50: 50 },
  macd: { fast: 12, slow: 26, signal: 9 },
  rsiPeriod: 14,
};

export const INDICATOR_PARAM_MIN = 1;
export const INDICATOR_PARAM_MAX = 250;

const INDICATOR_PARAMS_KEY = "tradingagents_indicator_params";

function defaultParams(): IndicatorParams {
  return {
    ma: { ...DEFAULT_INDICATOR_PARAMS.ma },
    macd: { ...DEFAULT_INDICATOR_PARAMS.macd },
    rsiPeriod: DEFAULT_INDICATOR_PARAMS.rsiPeriod,
  };
}

/** Coerce to an integer within [min, max], falling back when invalid. */
export function sanitizePeriod(value: unknown, fallback: number): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || !Number.isInteger(n)) return fallback;
  if (n < INDICATOR_PARAM_MIN || n > INDICATOR_PARAM_MAX) return fallback;
  return n;
}

export function loadIndicatorParams(): IndicatorParams {
  const params = defaultParams();
  try {
    const raw = localStorage.getItem(INDICATOR_PARAMS_KEY);
    if (!raw) return params;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      if (parsed.ma && typeof parsed.ma === "object") {
        (["ma5", "ma10", "ma20", "ma50"] as const).forEach((k) => {
          params.ma[k] = sanitizePeriod(parsed.ma[k], params.ma[k]);
        });
      }
      if (parsed.macd && typeof parsed.macd === "object") {
        (["fast", "slow", "signal"] as const).forEach((k) => {
          params.macd[k] = sanitizePeriod(parsed.macd[k], params.macd[k]);
        });
        if (params.macd.slow <= params.macd.fast) params.macd = { ...DEFAULT_INDICATOR_PARAMS.macd };
      }
      params.rsiPeriod = sanitizePeriod(parsed.rsiPeriod, params.rsiPeriod);
    }
  } catch {
    // corrupted JSON falls back to defaults
  }
  return params;
}

export function saveIndicatorParams(params: IndicatorParams): void {
  try {
    localStorage.setItem(INDICATOR_PARAMS_KEY, JSON.stringify(params));
  } catch {
    // persistence is best-effort
  }
}

// ── Frontend indicator recompute (parity with backend) ──────────────────────

/**
 * pandas ewm(adjust=True) mean, written as the equivalent running
 * numerator/denominator recursion:  y_t = (x_t + (1-α)·num) / (1 + (1-α)·den).
 * With span=window this is exactly stockstats' `ema()`, which is what the
 * backend uses for MACD, so values agree to float precision.
 */
function emaAdjust(values: number[], span: number): number[] {
  const a = 2 / (span + 1);
  const out: number[] = new Array(values.length);
  let num = 0;
  let den = 0;
  for (let i = 0; i < values.length; i++) {
    num = values[i] + (1 - a) * num;
    den = 1 + (1 - a) * den;
    out[i] = num / den;
  }
  return out;
}

/** stockstats' `smma()`: ewm(alpha=1/window, adjust=True). */
function smmaAdjust(values: number[], window: number): number[] {
  const a = 1 / window;
  const out: number[] = new Array(values.length);
  let num = 0;
  let den = 0;
  for (let i = 0; i < values.length; i++) {
    num = values[i] + (1 - a) * num;
    den = 1 + (1 - a) * den;
    out[i] = num / den;
  }
  return out;
}

/**
 * Simple moving average with null warm-up, mirroring the backend's
 * `_compute_ma` (values are left unrounded; display rounds to 2 decimals,
 * so |frontend − backend| stays ≤ 0.005).
 */
export function computeSmaSeries(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(closes.length).fill(null);
  let sum = 0;
  for (let i = 0; i < closes.length; i++) {
    sum += closes[i];
    if (i >= period) sum -= closes[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

/**
 * MACD (fast/slow/signal) on close prices, matching stockstats' formula:
 * MACD = EMA_fast − EMA_slow, signal = EMA_signal(MACD), hist = MACD − signal.
 * All series are defined from the first bar (adjust=True EMAs).
 */
export function computeMacdSeries(
  closes: number[],
  params: MacdParams,
): { macd: number[]; signal: number[]; histogram: number[] } {
  const emaFast = emaAdjust(closes, params.fast);
  const emaSlow = emaAdjust(closes, params.slow);
  const macd = closes.map((_, i) => emaFast[i] - emaSlow[i]);
  const signal = emaAdjust(macd, params.signal);
  const histogram = macd.map((v, i) => v - signal[i]);
  return { macd, signal, histogram };
}

/**
 * RSI over `period` bars, matching stockstats' formula: SMMA-smoothed
 * (alpha = 1/period) up/down moves, RSI = 100·up/(up+down); flat windows
 * yield 50. The first bar has no change and maps to 50, like the backend.
 */
export function computeRsiSeries(closes: number[], period: number): number[] {
  const n = closes.length;
  const up: number[] = new Array(n);
  const down: number[] = new Array(n);
  up[0] = 0;
  down[0] = 0;
  for (let i = 1; i < n; i++) {
    const diff = closes[i] - closes[i - 1];
    up[i] = diff > 0 ? diff : 0;
    down[i] = diff < 0 ? -diff : 0;
  }
  const upS = smmaAdjust(up, period);
  const downS = smmaAdjust(down, period);
  const out: number[] = new Array(n);
  for (let i = 0; i < n; i++) {
    const total = upS[i] + downS[i];
    out[i] = total !== 0 ? (100 * upS[i]) / total : 50;
  }
  if (n > 0) out[0] = 50;
  return out;
}

// ── Sub-panel indicators ────────────────────────────────────────────────────

/** Indicators selectable in each sub-panel slot. */
export type SubIndicatorKey = "MACD" | "RSI" | "Bollinger" | "KDJ" | "WR" | "CCI";

export const SUB_INDICATORS: { key: SubIndicatorKey; label: string }[] = [
  { key: "MACD", label: "MACD" },
  { key: "RSI", label: "RSI" },
  { key: "Bollinger", label: "BOLL" },
  { key: "KDJ", label: "KDJ" },
  { key: "WR", label: "WR" },
  { key: "CCI", label: "CCI" },
];

/**
 * Williams %R, computed purely on the frontend from OHLC.
 * WR = (HH − Close) / (HH − LL) × 100 over a rolling window; 0–100 range.
 * The first `period − 1` bars are null. ohlc rows are [open, close, low, high].
 */
export function computeWR(data: KlineData, period = 14): (number | null)[] {
  const ohlc = data.ohlc ?? [];
  const out: (number | null)[] = new Array(ohlc.length).fill(null);
  for (let i = period - 1; i < ohlc.length; i++) {
    let hh = -Infinity;
    let ll = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      if (ohlc[j][3] > hh) hh = ohlc[j][3];
      if (ohlc[j][2] < ll) ll = ohlc[j][2];
    }
    if (hh === ll) continue; // flat window — leave null rather than divide by zero
    const close = ohlc[i][1];
    out[i] = ((hh - close) / (hh - ll)) * 100;
  }
  return out;
}

/**
 * Commodity Channel Index, computed purely on the frontend from OHLC.
 * TP = (H + L + C) / 3; CCI = (TP − SMA(TP)) / (0.015 × mean|TP − SMA(TP)|).
 * The first `period − 1` bars are null. ohlc rows are [open, close, low, high].
 */
export function computeCCI(data: KlineData, period = 20): (number | null)[] {
  const ohlc = data.ohlc ?? [];
  const tp = ohlc.map((row) => (row[3] + row[2] + row[1]) / 3);
  const out: (number | null)[] = new Array(ohlc.length).fill(null);
  for (let i = period - 1; i < ohlc.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += tp[j];
    const sma = sum / period;
    let devSum = 0;
    for (let j = i - period + 1; j <= i; j++) devSum += Math.abs(tp[j] - sma);
    const meanDev = devSum / period;
    if (meanDev === 0) continue;
    out[i] = (tp[i] - sma) / (0.015 * meanDev);
  }
  return out;
}
