/**
 * Shared ECharts dark theme matching the TradingView-style palette.
 *
 * Usage:
 *   import { CHART_THEME } from "@/lib/echarts-theme";
 *   echarts.registerTheme("trading-dark", CHART_THEME);
 */

export const CHART_THEME = {
  backgroundColor: "transparent",
  textStyle: { color: "#D1D4DC" },
  title: { textStyle: { color: "#D1D4DC" } },
  legend: { textStyle: { color: "#787B86" } },
  tooltip: {
    backgroundColor: "rgba(30,34,45,0.95)",
    borderColor: "#363A45",
    textStyle: { color: "#D1D4DC", fontSize: 12 },
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: "#363A45" } },
    axisTick: { lineStyle: { color: "#363A45" } },
    axisLabel: { color: "#787B86" },
    splitLine: { lineStyle: { color: "#1E222D" } },
  },
  valueAxis: {
    axisLine: { lineStyle: { color: "#363A45" } },
    axisTick: { lineStyle: { color: "#363A45" } },
    axisLabel: { color: "#787B86" },
    splitLine: { lineStyle: { color: "#2A2E39" } },
  },
};

/** Standard color palette for charts */
export const CHART_COLORS = {
  green: "#089981",     // Buy / bullish / positive
  red: "#F23645",       // Sell / bearish / negative
  blue: "#2962FF",      // Accent / neutral line
  orange: "#FF6D00",    // Warning / main force
  gray: "#787B86",      // Muted / retail
  purple: "#9B59B6",    // Secondary accent
  yellow: "#F7B731",    // Highlight
};

/** Signal → color mapping */
export const SIGNAL_COLORS: Record<string, string> = {
  Buy: CHART_COLORS.green,
  Overweight: CHART_COLORS.orange,
  Hold: CHART_COLORS.gray,
  Underweight: "#EF5350",
  Sell: CHART_COLORS.red,
};
