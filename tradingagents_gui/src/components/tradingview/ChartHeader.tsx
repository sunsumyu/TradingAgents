/**
 * ChartHeader - Displays ticker info, price, and change.
 * TradingView-style header bar at the top of the chart.
 *
 * The price readout flashes green/red for ~1s whenever the realtime price
 * ticks up/down (ticket 11) - matching TradingView/futunn behavior. While
 * the crosshair is active the readout shows bar data instead, and the hook
 * is paused (null) so mouse movement never strobes the flash.
 */

import { useEffect, useRef } from "react";
import { Bell, LayoutGrid } from "lucide-react";
import type { CrosshairInfo } from "./types";
import { COLORS } from "./chart-theme";

interface Props {
  ticker: string;
  name?: string;
  crosshairInfo: CrosshairInfo | null;
  latestPrice?: number;
  latestChange?: number;
  latestChangePercent?: number;
  alertCount?: number;
  onToggleAlerts?: () => void;
  isMultiChart?: boolean;
  onToggleMultiChart?: () => void;
}

/** Background flash on realtime price ticks: direction-colored, ~1s fade-out. */
function usePriceFlash(value: number | null): React.RefObject<HTMLSpanElement> {
  const priceRef = useRef<HTMLSpanElement>(null);
  const prevPrice = useRef<number | null>(null);

  useEffect(() => {
    const el = priceRef.current;
    if (!el || value == null) return;
    const prev = prevPrice.current;
    prevPrice.current = value;
    if (prev == null || value === prev) return; // first value / no tick

    el.style.transition = "none";
    el.style.backgroundColor = value > prev ? "rgba(8,153,129,0.25)" : "rgba(242,54,69,0.25)";
    // Double rAF guarantees the browser paints the flash color before the
    // transition to transparent is scheduled.
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        el.style.transition = "background-color 1s";
        el.style.backgroundColor = "transparent";
      }),
    );
  }, [value]);

  return priceRef;
}

export default function ChartHeader({
  ticker,
  name,
  crosshairInfo,
  latestPrice,
  latestChange,
  latestChangePercent,
  alertCount = 0,
  onToggleAlerts,
  isMultiChart = false,
  onToggleMultiChart,
}: Props) {
  const info = crosshairInfo;

  const price = info?.close ?? latestPrice ?? 0;
  const change = info?.change ?? latestChange ?? 0;
  const changePct = info?.changePercent ?? latestChangePercent ?? 0;
  const isPositive = change >= 0;

  const changeColor = isPositive ? COLORS.up : COLORS.down;
  const changeSign = isPositive ? "+" : "";

  // Flash reacts to realtime ticks only; crosshair mode passes null (paused).
  const priceRef = usePriceFlash(crosshairInfo ? null : (latestPrice ?? null));

  return (
    <div className="flex items-center gap-4 px-4 h-9 bg-[#131722] border-b border-[#2B2B43] text-xs select-none">
      {/* Ticker */}
      <span className="font-semibold text-[#D1D4DC] text-sm">{ticker}</span>

      {/* Name */}
      {name && <span className="text-[#787B86]">{name}</span>}

      {/* Separator */}
      <span className="text-[#2B2B43]">·</span>

      {/* Price (flashes on tick) */}
      <span
        ref={priceRef}
        style={{ color: changeColor }}
        className="font-mono font-medium rounded px-1"
      >
        {price.toFixed(2)}
      </span>

      {/* Change */}
      <span style={{ color: changeColor }} className="font-mono">
        {changeSign}{change.toFixed(2)}
      </span>

      {/* Change % */}
      <span style={{ color: changeColor }} className="font-mono">
        ({changeSign}{changePct.toFixed(2)}%)
      </span>

      {/* Crosshair data (fills right side when hovering) */}
      {info && (
        <div className="ml-auto flex items-center gap-3 text-[#787B86] font-mono">
          <span>O <span className="text-[#D1D4DC]">{info.open.toFixed(2)}</span></span>
          <span>H <span className="text-[#D1D4DC]">{info.high.toFixed(2)}</span></span>
          <span>L <span className="text-[#D1D4DC]">{info.low.toFixed(2)}</span></span>
          <span>C <span className="text-[#D1D4DC]">{info.close.toFixed(2)}</span></span>
          {info.volume > 0 && (
            <span>Vol <span className="text-[#D1D4DC]">{formatVolume(info.volume)}</span></span>
          )}
        </div>
      )}

      {/* Spacer when no crosshair — pushes bell to right */}
      {!info && <div className="ml-auto" />}

      {/* Multi-chart toggle */}
      {onToggleMultiChart && (
        <button
          onClick={onToggleMultiChart}
          className={`p-1 rounded transition-colors ${
            isMultiChart ? "bg-[#2962FF]/20 text-[#2962FF]" : "hover:bg-[#2A2E39] text-[#787B86]"
          }`}
          title={isMultiChart ? "单图表模式" : "多图表布局"}
        >
          <LayoutGrid size={13} />
        </button>
      )}

      {/* Price alert bell */}
      {onToggleAlerts && (
        <button
          onClick={onToggleAlerts}
          className="relative p-1 rounded hover:bg-[#2A2E39] transition-colors"
          title="价格预警"
        >
          <Bell size={13} className="text-[#787B86]" />
          {alertCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] flex items-center justify-center rounded-full bg-[#2962FF] text-[8px] text-white px-0.5 font-medium">
              {alertCount}
            </span>
          )}
        </button>
      )}
    </div>
  );
}

function formatVolume(v: number): string {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(2)}万`;
  return v.toFixed(0);
}
