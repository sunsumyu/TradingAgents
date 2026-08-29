/**
 * SubPanelHeader — title + indicator-switch dropdown for a sub-panel slot.
 *
 * Lists all six sub-panel indicators (MACD/RSI/BOLL/KDJ/WR/CCI); entries whose
 * data is unavailable are shown but disabled (grayed out). Click-outside and
 * Escape both close the menu.
 */

import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { SUB_INDICATORS, type SubIndicatorKey } from "../../lib/chart-utils";

interface Props {
  current: SubIndicatorKey;
  available: Set<SubIndicatorKey>;
  /** Latest-value readout shown beside the title (already formatted). */
  detail?: string;
  onSelect: (key: SubIndicatorKey) => void;
  /** When set (MACD/RSI), right-clicking the title opens the param dialog. */
  onOpenParams?: () => void;
}

export default function SubPanelHeader({ current, available, detail, onSelect, onOpenParams }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Close on outside click / Escape while open
  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onMouseDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="absolute top-1 left-2 z-10 select-none">
      <button
        onClick={() => setOpen((o) => !o)}
        onContextMenu={(e) => {
          if (!onOpenParams) return;
          e.preventDefault();
          onOpenParams();
        }}
        className="flex items-center gap-0.5 text-[9px] text-[#787B86] hover:text-[#D1D4DC] transition-colors"
        title={onOpenParams ? "切换指标 · 右键设置参数" : "切换指标"}
      >
        {current}
        {detail && <span className="ml-1 tabular-nums">{detail}</span>}
        <ChevronDown size={9} />
      </button>

      {open && (
        <div className="absolute top-4 left-0 min-w-[88px] py-1 rounded bg-[#1E222D] border border-[#2B2B43] shadow-lg z-20">
          {SUB_INDICATORS.map(({ key, label }) => {
            const enabled = available.has(key);
            const isCurrent = key === current;
            return (
              <button
                key={key}
                disabled={!enabled}
                onClick={() => {
                  onSelect(key);
                  setOpen(false);
                }}
                title={enabled ? undefined : "暂无数据"}
                className={`block w-full text-left px-3 py-1 text-[10px] transition-colors ${
                  isCurrent
                    ? "text-[#2962FF]"
                    : enabled
                      ? "text-[#D1D4DC] hover:bg-[#2A2E39]"
                      : "text-[#4C525E] cursor-not-allowed"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
