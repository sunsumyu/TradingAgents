/**
 * SubPanels — 3-slot sub-indicator grid below the main chart.
 *
 * Each slot is independently switchable among MACD/RSI/BOLL/KDJ/WR/CCI.
 * Slot configuration is persisted to localStorage.
 *
 * Extracted from TradingViewLayout.tsx (ticket 8.01).
 */

import { useState, useCallback, useMemo } from "react";
import type { KlineData, MacdData, RsiData, BollingerData } from "../../lib/types";
import type { IndicatorParams } from "../../lib/chart-utils";
import { computeWR, computeCCI, SUB_INDICATORS, type SubIndicatorKey } from "../../lib/chart-utils";
import SubPanelHeader from "./SubPanelHeader";
import IndicatorParamDialog, { type ParamTarget } from "./IndicatorParamDialog";
import { SubIndicatorPanel } from "./SubIndicatorMinis";

// ── Constants ───────────────────────────────────────────────────────────────

const SUB_SLOTS_KEY = "tradingagents_subpanel_indicators";
const DEFAULT_SLOTS: SubIndicatorKey[] = ["MACD", "RSI", "KDJ"];

// ── Helpers ─────────────────────────────────────────────────────────────────

function loadSubSlots(): SubIndicatorKey[] {
  try {
    const raw = localStorage.getItem(SUB_SLOTS_KEY);
    if (!raw) return DEFAULT_SLOTS;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length === 3) {
      return parsed.filter((k) => SUB_INDICATORS.some(({ key }) => key === k));
    }
  } catch {
    // fall through to defaults
  }
  return DEFAULT_SLOTS;
}

/** Which sub-indicators have data for the given chart inputs. */
function availableIndicators(
  kline: KlineData | null,
  macd?: MacdData | null,
  rsi?: RsiData | null,
  bollinger?: BollingerData | null,
): Set<SubIndicatorKey> {
  const avail = new Set<SubIndicatorKey>();
  if (macd) avail.add("MACD");
  if (rsi) avail.add("RSI");
  if (bollinger) avail.add("Bollinger");
  if (kline?.kdj_k?.length) avail.add("KDJ");
  if (kline?.ohlc?.length) {
    avail.add("WR");
    avail.add("CCI");
  }
  return avail;
}

/** Latest-value readout shown in each slot's header (already formatted). */
function subIndicatorDetail(
  key: SubIndicatorKey,
  kline: KlineData | null,
  macd?: MacdData | null,
  rsi?: RsiData | null,
): string | undefined {
  const last = (arr?: (number | null)[]) => {
    if (!arr || arr.length === 0) return undefined;
    const v = arr[arr.length - 1];
    return v != null ? v.toFixed(2) : undefined;
  };
  switch (key) {
    case "MACD":
      return macd?.macd?.length ? last(macd.macd) : undefined;
    case "RSI":
      return rsi?.values?.length ? last(rsi.values) : undefined;
    case "KDJ": {
      if (!kline?.kdj_k?.length) return undefined;
      const fmt = (arr?: (number | null)[]) => last(arr)?.replace(/\.00$/, "") ?? "—";
      return `K:${fmt(kline.kdj_k)} D:${fmt(kline.kdj_d)} J:${fmt(kline.kdj_j)}`;
    }
    case "WR":
      return kline?.ohlc?.length ? last(computeWR(kline)) : undefined;
    case "CCI":
      return kline?.ohlc?.length ? last(computeCCI(kline)) : undefined;
    default:
      return undefined;
  }
}

// ── Component ───────────────────────────────────────────────────────────────

interface Props {
  kline: KlineData | null;
  macd?: MacdData | null;
  rsi?: RsiData | null;
  bollinger?: BollingerData | null;
  crosshairTime?: string | null;
  params: IndicatorParams;
  onApplyParams: (params: IndicatorParams) => void;
}

export default function SubPanels({
  kline,
  macd,
  rsi,
  bollinger,
  crosshairTime,
  params,
  onApplyParams,
}: Props) {
  const [slots, setSlots] = useState<SubIndicatorKey[]>(loadSubSlots);
  const [paramDialog, setParamDialog] = useState<ParamTarget | null>(null);

  const available = useMemo(
    () => availableIndicators(kline, macd, rsi, bollinger),
    [kline, macd, rsi, bollinger],
  );

  // Recomputed on data change; small enough to be cheap even at ALL timeframe
  const details = useMemo(() => {
    const map = new Map<SubIndicatorKey, string>();
    for (const { key } of SUB_INDICATORS) {
      const d = subIndicatorDetail(key, kline, macd, rsi);
      if (d != null) map.set(key, d);
    }
    return map;
  }, [kline, macd, rsi]);

  const handleSelect = useCallback((slotIndex: number, key: SubIndicatorKey) => {
    setSlots((prev) => {
      // Picking an indicator already shown in another slot swaps the two slots
      const existingIdx = prev.findIndex((k, i) => k === key && i !== slotIndex);
      const next = [...prev];
      if (existingIdx >= 0) next[existingIdx] = prev[slotIndex];
      next[slotIndex] = key;
      try {
        localStorage.setItem(SUB_SLOTS_KEY, JSON.stringify(next));
      } catch {
        // ignore persistence failures
      }
      return next;
    });
  }, []);

  return (
    <div className="border-t border-[#2B2B43] bg-[#131722]" style={{ height: 180 }}>
      <div
        className="grid h-full gap-0"
        style={{ gridTemplateColumns: "repeat(3, 1fr)" }}
      >
        {slots.map((key, i) => (
          <div key={i} className={`relative h-full ${i > 0 ? "border-l border-[#2B2B43]" : ""}`}>
            <SubPanelHeader
              current={key}
              available={available}
              detail={details.get(key)}
              onSelect={(k) => handleSelect(i, k)}
              onOpenParams={key === "MACD" || key === "RSI" ? () => setParamDialog(key) : undefined}
            />
            <SubIndicatorPanel
              indicator={key}
              kline={kline}
              macd={macd}
              rsi={rsi}
              bollinger={bollinger}
              crosshairTime={crosshairTime}
            />
          </div>
        ))}
      </div>
      {paramDialog && (
        <IndicatorParamDialog
          target={paramDialog}
          params={params}
          onApply={onApplyParams}
          onClose={() => setParamDialog(null)}
        />
      )}
    </div>
  );
}
