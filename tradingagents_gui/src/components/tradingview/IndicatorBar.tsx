/**
 * IndicatorBar - Overlay indicator toggle bar above the main chart.
 *
 * TradingView-style: each indicator is a button showing its latest value
 * (e.g. "MA5 23.45"), colored to match its line on the chart. Left-click
 * toggles visibility; active indicators have a colored border, inactive
 * ones are muted gray. Right-click (or the ⚙ button) opens the parameter
 * dialog for MA / MACD / RSI.
 */

import { useState } from "react";
import { Settings } from "lucide-react";
import type { KlineData } from "../../lib/types";
import {
  OVERLAY_INDICATORS,
  getLatestIndicatorValue,
  type IndicatorKey,
  type IndicatorParams,
} from "../../lib/chart-utils";
import IndicatorParamDialog, { type ParamTarget } from "./IndicatorParamDialog";

interface Props {
  data: KlineData | null;
  activeOverlays: string[];
  onToggleOverlay: (key: string) => void;
  /** Adjustable params (MA periods shown in labels). */
  params: IndicatorParams;
  onApplyParams: (params: IndicatorParams) => void;
  /** Computed MA series by activeOverlay key; falls back to kline fields. */
  maSeries?: Record<string, (number | null)[]>;
}

export default function IndicatorBar({
  data,
  activeOverlays,
  onToggleOverlay,
  params,
  onApplyParams,
  maSeries,
}: Props) {
  const [dialog, setDialog] = useState<ParamTarget | null>(null);
  if (!data) return null;

  const latestFromSeries = (key: string, field: keyof KlineData): string => {
    const series = maSeries?.[key];
    if (series && series.length > 0) {
      const v = series[series.length - 1];
      return v != null ? v.toFixed(2) : "-";
    }
    return getLatestIndicatorValue(data, field);
  };

  const maLabel = (key: string): string => {
    if (key === "ma5") return `MA(${params.ma.ma5})`;
    if (key === "ma10") return `MA(${params.ma.ma10})`;
    if (key === "ma20") return `MA(${params.ma.ma20})`;
    if (key === "ma50") return `MA(${params.ma.ma50})`;
    return key.toUpperCase();
  };

  const openDialogFor = (key: string): ParamTarget | null => {
    if (key.startsWith("ma") || key.startsWith("ema")) return "MA";
    return null;
  };

  return (
    <div className="flex items-center gap-1.5 px-3 h-7 bg-[#131722] border-b border-[#2B2B43] select-none overflow-x-auto">
      {OVERLAY_INDICATORS.map(({ key, field, color }) => {
        const overlayKey = key.toLowerCase();
        const label = overlayKey.startsWith("ma") ? maLabel(overlayKey) : key;
        return (
          <IndicatorButton
            key={key}
            indicatorKey={key}
            label={label}
            color={color}
            value={latestFromSeries(overlayKey, field)}
            active={activeOverlays.includes(key)}
            onToggle={() => onToggleOverlay(key)}
            onContextMenu={(e) => {
              const target = openDialogFor(overlayKey);
              if (!target) return;
              e.preventDefault();
              setDialog(target);
            }}
          />
        );
      })}

      <button
        onClick={() => setDialog("MA")}
        className="ml-1 p-0.5 rounded text-[#787B86] hover:text-[#D1D4DC] hover:bg-[#2A2E39] transition-colors shrink-0"
        title="指标参数设置"
      >
        <Settings size={12} />
      </button>

      {dialog && (
        <IndicatorParamDialog
          target={dialog}
          params={params}
          onApply={onApplyParams}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}

// ── Single indicator button ─────────────────────────────────────────────────

function IndicatorButton({
  indicatorKey,
  label,
  color,
  value,
  active,
  onToggle,
  onContextMenu,
}: {
  indicatorKey: IndicatorKey;
  label: string;
  color: string;
  value: string;
  active: boolean;
  onToggle: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
}) {
  return (
    <button
      onClick={onToggle}
      onContextMenu={onContextMenu}
      className="px-1.5 py-0.5 rounded text-[11px] whitespace-nowrap transition-colors"
      style={{
        color: active ? color : "#555",
        border: `1px solid ${active ? color : "transparent"}`,
        background: "transparent",
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.color = "#787B86";
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.color = "#555";
      }}
      title={`${active ? "隐藏" : "显示"} ${indicatorKey} · 右键设置参数`}
    >
      {label} <span style={{ opacity: 0.8 }}>{value}</span>
    </button>
  );
}
