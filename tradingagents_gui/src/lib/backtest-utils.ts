/**
 * Pure helpers for the report-page backtest entry (ticket #6).
 *
 * The GUI never computes metrics itself; it only maps the report signal to
 * an engine decision, derives the request window from the analysis date,
 * and normalizes server equity curves for charting.
 */

import type { EquityPoint } from "./types";

/** Holding-day ladder offered in the GUI for comparison runs. */
export const HOLDING_DAY_OPTIONS = [1, 3, 5, 10] as const;

/** Map the report's signal badge to an engine decision. */
export function signalToDecision(signal: string): "BUY" | "SELL" | "HOLD" {
  switch (signal) {
    case "Buy":
    case "Overweight":
      return "BUY";
    case "Sell":
    case "Underweight":
      return "SELL";
    default:
      return "HOLD";
  }
}

/**
 * Backtest window for a given analysis date and holding period.
 *
 * start = the analysis date (entry point), end = start + 2*holdingDays + 10
 * calendar days; akshare truncates to the last available trading day.
 */
export function backtestWindow(
  analysisDate: string,
  holdingDays: number,
): { start: string; end: string } {
  const start = new Date(`${analysisDate}T00:00:00Z`);
  if (Number.isNaN(start.getTime())) {
    return { start: analysisDate, end: analysisDate };
  }
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + holdingDays * 2 + 10);
  return {
    start: analysisDate,
    end: end.toISOString().slice(0, 10),
  };
}

/**
 * Normalize an equity curve to cumulative return % from the first point.
 *
 * Returns [date, percent] pairs ready for ECharts line series. Curves with
 * fewer than 2 points or a zero/non-finite base yield [].
 */
export function normalizeCurve(
  curve: EquityPoint[],
): [string, number][] {
  if (curve.length < 2) return [];
  const base = curve[0].value;
  if (!Number.isFinite(base) || base === 0) return [];
  const out: [string, number][] = [];
  for (const p of curve) {
    if (!Number.isFinite(p.value)) continue;
    out.push([p.date, ((p.value - base) / base) * 100]);
  }
  return out;
}

/** True when an error message is the missing-dependency guidance case. */
export function isInstallGuidanceError(message: string): boolean {
  const m = message.toLowerCase();
  return m.includes("akquant") || m.includes("pip install");
}

/** Format a fraction (0.12) as a signed percent string ("+12.0%"). */
export function formatPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

/** Format a plain ratio (1.45) with 2 decimals, "-" for null. */
export function formatRatio(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return value.toFixed(2);
}
