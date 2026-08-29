/**
 * TimeframeSelector — Horizontal button group for switching timeframes.
 * TradingView-style timeframe bar: minute intervals first (intraday), then
 * day-based ranges.
 */

import type { Timeframe } from "./types";

const TIMEFRAMES: Timeframe[] = ["1m", "5m", "15m", "30m", "60m", "1D", "1W", "1M", "3M", "1Y", "ALL"];

const TIMEFRAME_LABELS: Record<Timeframe, string> = {
  "1m": "1分",
  "5m": "5分",
  "15m": "15分",
  "30m": "30分",
  "60m": "60分",
  "1D": "1D",
  "1W": "1W",
  "1M": "1M",
  "3M": "3M",
  "1Y": "1Y",
  "ALL": "ALL",
};

interface Props {
  current: Timeframe;
  onChange: (tf: Timeframe) => void;
}

export default function TimeframeSelector({ current, onChange }: Props) {
  return (
    <div className="flex items-center gap-0.5 px-3 h-8 bg-[#131722] border-b border-[#2B2B43] select-none">
      {TIMEFRAMES.map((tf) => {
        const active = tf === current;
        return (
          <button
            key={tf}
            onClick={() => onChange(tf)}
            className="px-2 py-1 text-xs font-medium rounded transition-colors"
            style={{
              color: active ? "#D1D4DC" : "#787B86",
              backgroundColor: active ? "#2A2E39" : "transparent",
            }}
            onMouseEnter={(e) => {
              if (!active) e.currentTarget.style.color = "#D1D4DC";
            }}
            onMouseLeave={(e) => {
              if (!active) e.currentTarget.style.color = "#787B86";
            }}
          >
            {TIMEFRAME_LABELS[tf]}
          </button>
        );
      })}
    </div>
  );
}
