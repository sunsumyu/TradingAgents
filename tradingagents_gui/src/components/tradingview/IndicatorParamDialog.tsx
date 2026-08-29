/**
 * IndicatorParamDialog - TradingView-style settings dialog for indicator
 * parameters (MA periods, MACD fast/slow/signal, RSI period).
 *
 * Inputs are validated as integers within [1, 250]; OK stays disabled until
 * every field is valid. 「重置默认」restores defaults and applies them
 * immediately. Escape cancels back to the persisted values.
 */

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import {
  DEFAULT_INDICATOR_PARAMS,
  INDICATOR_PARAM_MAX,
  INDICATOR_PARAM_MIN,
  type IndicatorParams,
} from "../../lib/chart-utils";

export type ParamTarget = "MA" | "MACD" | "RSI";

interface FieldDef {
  key: string;
  label: string;
  value: number;
}

interface Props {
  target: ParamTarget;
  params: IndicatorParams;
  onApply: (params: IndicatorParams) => void;
  onClose: () => void;
}

const TITLES: Record<ParamTarget, string> = {
  MA: "移动平均线 MA 设置",
  MACD: "MACD 设置",
  RSI: "RSI 设置",
};

function fieldsFor(target: ParamTarget, params: IndicatorParams): FieldDef[] {
  if (target === "MA") {
    return [
      { key: "ma5", label: "MA1 周期", value: params.ma.ma5 },
      { key: "ma10", label: "MA2 周期", value: params.ma.ma10 },
      { key: "ma20", label: "MA3 周期", value: params.ma.ma20 },
      { key: "ma50", label: "MA4 周期", value: params.ma.ma50 },
    ];
  }
  if (target === "MACD") {
    return [
      { key: "fast", label: "快线 EMA 周期", value: params.macd.fast },
      { key: "slow", label: "慢线 EMA 周期", value: params.macd.slow },
      { key: "signal", label: "信号线 EMA 周期", value: params.macd.signal },
    ];
  }
  return [{ key: "rsiPeriod", label: "RSI 周期", value: params.rsiPeriod }];
}

export default function IndicatorParamDialog({ target, params, onApply, onClose }: Props) {
  const [draft, setDraft] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const f of fieldsFor(target, params)) init[f.key] = String(f.value);
    return init;
  });

  // Escape closes without applying
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const fields = fieldsFor(target, params);

  /** '' while the raw input is not a valid integer in range. */
  const validated = fields.map((f) => {
    const raw = draft[f.key];
    const n = Number(raw);
    const ok =
      raw !== "" &&
      Number.isFinite(n) &&
      Number.isInteger(n) &&
      n >= INDICATOR_PARAM_MIN &&
      n <= INDICATOR_PARAM_MAX;
    return { ...f, raw, valid: ok, value: ok ? n : 0 };
  });
  const allValid = validated.every((f) => f.valid);
  const anyMacdIssue =
    target === "MACD" &&
    allValid &&
    Number(validated.find((f) => f.key === "slow")?.value) <=
      Number(validated.find((f) => f.key === "fast")?.value);
  const canApply = allValid && !anyMacdIssue;

  const buildNextParams = (): IndicatorParams => {
    const next: IndicatorParams = {
      ma: { ...params.ma },
      macd: { ...params.macd },
      rsiPeriod: params.rsiPeriod,
    };
    for (const f of validated) {
      if (!f.valid) continue;
      if (target === "MA") (next.ma as unknown as Record<string, number>)[f.key] = f.value;
      else if (target === "MACD") (next.macd as unknown as Record<string, number>)[f.key] = f.value;
      else if (f.key === "rsiPeriod") next.rsiPeriod = f.value;
    }
    return next;
  };

  const handleReset = () => {
    onApply({
      ma: { ...DEFAULT_INDICATOR_PARAMS.ma },
      macd: { ...DEFAULT_INDICATOR_PARAMS.macd },
      rsiPeriod: DEFAULT_INDICATOR_PARAMS.rsiPeriod,
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 bg-black/40" onMouseDown={onClose}>
      <div
        className="w-[320px] rounded-lg bg-[#1E222D] border border-[#2B2B43] shadow-2xl select-none"
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 h-10 border-b border-[#2B2B43]">
          <span className="text-[13px] text-[#D1D4DC] font-medium">{TITLES[target]}</span>
          <button onClick={onClose} className="p-1 rounded hover:bg-[#2A2E39] transition-colors" title="关闭">
            <X size={14} className="text-[#787B86]" />
          </button>
        </div>

        {/* Fields */}
        <div className="px-4 py-3 flex flex-col gap-2.5">
          {validated.map((f) => (
            <label key={f.key} className="flex items-center justify-between gap-3">
              <span className="text-[12px] text-[#787B86] whitespace-nowrap">{f.label}</span>
              <input
                type="number"
                min={INDICATOR_PARAM_MIN}
                max={INDICATOR_PARAM_MAX}
                step={1}
                value={f.raw}
                onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                className={`w-[110px] px-2 py-1 rounded text-[12px] tabular-nums bg-[#131722] border ${
                  f.valid ? "border-[#2B2B43]" : "border-[#F23645]"
                } text-[#D1D4DC] outline-none focus:border-[#2962FF] transition-colors`}
              />
            </label>
          ))}
          {anyMacdIssue && (
            <div className="text-[11px] text-[#F23645]">慢线周期需大于快线周期</div>
          )}
          {!allValid && (
            <div className="text-[11px] text-[#787B86]">
              请输入 {INDICATOR_PARAM_MIN}–{INDICATOR_PARAM_MAX} 之间的整数
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-[#2B2B43]">
          <button
            onClick={handleReset}
            className="px-3 py-1.5 rounded text-[12px] text-[#787B86] hover:text-[#D1D4DC] hover:bg-[#2A2E39] transition-colors"
          >
            重置默认
          </button>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded text-[12px] text-[#D1D4DC] hover:bg-[#2A2E39] transition-colors"
            >
              取消
            </button>
            <button
              disabled={!canApply}
              onClick={() => {
                onApply(buildNextParams());
                onClose();
              }}
              className={`px-4 py-1.5 rounded text-[12px] font-medium transition-colors ${
                canApply
                  ? "bg-[#2962FF] text-white hover:bg-[#1E53E5]"
                  : "bg-[#2A2E39] text-[#4C525E] cursor-not-allowed"
              }`}
            >
              确定
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
