/**
 * TradingView dark theme configuration for lightweight-charts.
 * Matches the existing TradingAgents dark palette.
 */

export const TRADING_VIEW_THEME = {
  layout: {
    background: { type: 0, color: "#131722" } as any, // ColorType.Solid
    textColor: "#D1D4DC",
    fontSize: 12,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    panes: {
      enableResize: true,
      separatorColor: "#2B2B43",
      separatorHoverColor: "rgba(178, 181, 189, 0.2)",
    },
  },
  grid: {
    vertLines: { color: "#1E222D" },
    horzLines: { color: "#1E222D" },
  },
  crosshair: {
    mode: 1 as const, // CrosshairMode.Magnet
    vertLine: {
      color: "#758696",
      width: 1,
      style: 3 as const, // LargeDashed
      labelBackgroundColor: "#4C525E",
    },
    horzLine: {
      color: "#758696",
      width: 1,
      style: 3 as const,
      labelBackgroundColor: "#4C525E",
    },
  },
  timeScale: {
    borderColor: "#2B2B43",
    timeVisible: true,
    secondsVisible: false,
  },
  rightPriceScale: {
    borderColor: "#2B2B43",
  },
  watermark: {
    visible: false,
  },
} as const;

// ── Series colors ───────────────────────────────────────────────────────────

export const COLORS = {
  up: "#089981",       // bullish candle
  down: "#F23645",     // bearish candle
  upWick: "#089981",
  downWick: "#F23645",
  volume: "#26A69A",   // default volume color (overridden per bar)

  // MA overlays
  ma5: "#2962FF",
  ma10: "#FF6D00",
  ma20: "#9B59B6",
  ma50: "#F7B731",
  ema12: "#089981",
  ema26: "#F23645",

  // UI
  text: "#D1D4DC",
  textMuted: "#787B86",
  border: "#2B2B43",
  cardBg: "#1E222D",
  hoverBg: "#2A2E39",
} as const;

// ── Overlay config ──────────────────────────────────────────────────────────

export const OVERLAY_CONFIG: Record<string, { color: string; lineWidth: number }> = {
  ma5: { color: COLORS.ma5, lineWidth: 1 },
  ma10: { color: COLORS.ma10, lineWidth: 1 },
  ma20: { color: COLORS.ma20, lineWidth: 1 },
  ma50: { color: COLORS.ma50, lineWidth: 1 },
  ema12: { color: COLORS.ema12, lineWidth: 1 },
  ema26: { color: COLORS.ema26, lineWidth: 1 },
};
