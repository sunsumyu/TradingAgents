/**
 * Shared ECharts theme configuration.
 * 
 * Import and merge with chart options for consistent styling.
 */

export const chartTheme = {
  // Colors
  colors: ["#ef4444", "#3b82f6", "#f59e0b", "#10b981", "#8b5cf6"],
  upColor: "#ef4444",
  downColor: "#22c55e",

  // Grid
  grid: { left: 50, right: 16, top: 28, bottom: 28 },

  // Tooltip
  tooltip: {
    backgroundColor: "#1e293b",
    borderColor: "#334155",
    textStyle: { color: "#e2e8f0", fontSize: 11 },
  },

  // Axes
  xAxis: {
    axisLine: { lineStyle: { color: "#334155" } },
    axisLabel: { color: "#64748b", fontSize: 10 },
    splitLine: { show: false },
  },
  yAxis: {
    axisLine: { lineStyle: { color: "#334155" } },
    axisLabel: { color: "#64748b", fontSize: 10 },
    splitLine: { lineStyle: { color: "#1e293b", type: "dashed" as const } },
  },

  // Legend
  legend: {
    textStyle: { color: "#94a3b8", fontSize: 10 },
  },
};

/** Merge user options with theme defaults */
export function withTheme(userOptions: any): any {
  return {
    animation: false,
    ...chartTheme,
    ...userOptions,
    xAxis: { ...chartTheme.xAxis, ...userOptions.xAxis },
    yAxis: { ...chartTheme.yAxis, ...userOptions.yAxis },
    tooltip: { ...chartTheme.tooltip, ...userOptions.tooltip },
    legend: { ...chartTheme.legend, ...userOptions.legend },
  };
}
