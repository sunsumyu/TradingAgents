/**
 * FinancialStatementPanel — Structured multi-period table + trend chart
 * for balance sheet, income statement, and cashflow reports.
 *
 * Layout (matches other astock panels — fills 320px fixed height):
 *  - Top: readout bar (period count + latest report date)
 *  - Middle: scrollable table with fixed "科目" column + horizontal periods
 *  - Bottom: ECharts trend chart of key items
 */

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { AstockFeatureKey, FinancialStatementData } from "../../lib/types";

interface Props {
  feature: AstockFeatureKey;
  data: FinancialStatementData;
  rawMd: string;
}

/** Key items to highlight in the trend chart per statement type. */
const HIGHLIGHTS: Record<string, { label: string; key: string }[]> = {
  balance_sheet: [
    { label: "资产合计", key: "资产合计" },
    { label: "负债合计", key: "负债合计" },
    { label: "股东权益", key: "股东权益合计" },
  ],
  income_statement: [
    { label: "营业收入", key: "营业收入" },
    { label: "净利润", key: "净利润" },
  ],
  cashflow: [
    { label: "经营现金流", key: "经营活动产生的现金流量净额" },
    { label: "投资现金流", key: "投资活动产生的现金流量净额" },
    { label: "筹资现金流", key: "筹资活动产生的现金流量净额" },
  ],
};

const CHART_COLORS = ["#2962FF", "#089981", "#F23645", "#FF6D00", "#9B59B6"];

function fmtValue(v: number | null): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (abs >= 1e4) return `${(v / 1e4).toFixed(1)}万`;
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function fmtShortPeriod(p: string): string {
  // "2026-06-30" → "26Q2", "2025-12-31" → "25年报"
  const m = p.match(/^(\d{4})-(\d{2})/);
  if (!m) return p;
  const yr = m[1].slice(-2);
  const month = parseInt(m[2], 10);
  if (month === 12) return `${yr}年报`;
  const q = Math.ceil(month / 3);
  return `${yr}Q${q}`;
}

export default function FinancialStatementPanel({ feature, data, rawMd }: Props) {
  const { periods, columns, items } = data;
  const highlights = HIGHLIGHTS[feature] ?? [];

  // Only show highlight items that actually exist in the data
  const activeHighlights = useMemo(
    () => highlights.filter((h) => items[h.key]?.some((v) => v != null)),
    [highlights, items],
  );

  // ── Trend chart option ────────────────────────────────────────────────────
  const chartOption = useMemo(() => {
    if (!periods.length || !activeHighlights.length) return null;
    const shortPeriods = periods.map(fmtShortPeriod);

    const series = activeHighlights.map((h, idx) => ({
      name: h.label,
      type: "line" as const,
      data: items[h.key] ?? [],
      lineStyle: { width: 1.5, color: CHART_COLORS[idx % CHART_COLORS.length] },
      itemStyle: { color: CHART_COLORS[idx % CHART_COLORS.length] },
      symbol: "circle",
      symbolSize: 4,
      showSymbol: periods.length <= 6,
    }));

    return {
      animation: false,
      backgroundColor: "transparent",
      grid: { left: 50, right: 15, top: 10, bottom: 24 },
      xAxis: {
        type: "category" as const,
        data: shortPeriods,
        axisLine: { lineStyle: { color: "#2B2B43" } },
        axisLabel: { color: "#787B86", fontSize: 9 },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value" as const,
        scale: true,
        axisLine: { lineStyle: { color: "#2B2B43" } },
        axisLabel: { color: "#787B86", fontSize: 9, formatter: (v: number) => fmtValue(v) },
        splitLine: { lineStyle: { color: "#1E222D" } },
      },
      tooltip: {
        trigger: "axis" as const,
        backgroundColor: "#1E222D",
        borderColor: "#2B2B43",
        textStyle: { color: "#D1D4DC", fontSize: 10 },
        formatter: (params: any[]) => {
          if (!params?.length) return "";
          let html = `<div style="font-family:monospace;font-size:10px"><div style="color:#787B86">${params[0].axisValue}</div>`;
          for (const p of params) {
            const val = p.value as number;
            html += `<div style="color:${p.color}">${p.seriesName}: ${val != null ? fmtValue(val) : "—"}</div>`;
          }
          return html + "</div>";
        },
      },
      series,
    };
  }, [periods, activeHighlights, items]);

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!periods.length) {
    return (
      <div className="h-full overflow-y-auto">
        {rawMd ? (
          <pre className="text-[11px] text-[#787B86] p-3 whitespace-pre-wrap leading-relaxed">
            {rawMd}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
            暂无财务数据
          </div>
        )}
      </div>
    );
  }

  const latestPeriod = periods[0] ?? "";

  return (
    <div className="h-full flex flex-col">
      {/* ── Readout bar ──────────────────────────────────────────────────── */}
      <div className="flex items-center gap-4 px-3 py-1.5 border-b border-[#2B2B43] text-[11px] shrink-0">
        <span className="text-[#787B86]">
          {periods.length} 期数据
        </span>
        <span className="text-[#787B86]">
          最新: <span className="text-[#D1D4DC] font-mono">{latestPeriod}</span>
        </span>
      </div>

      {/* ── Scrollable table ─────────────────────────────────────────────── */}
      <div className="overflow-x-auto overflow-y-auto flex-1 min-h-0">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-[10px] text-[#4C525E] border-b border-[#2B2B43]">
              <th className="sticky left-0 bg-[#131722] text-left px-2 py-1.5 font-medium z-10">
                科目
              </th>
              {periods.map((p) => (
                <th key={p} className="text-right px-2 py-1.5 font-mono font-medium whitespace-nowrap">
                  {fmtShortPeriod(p)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {columns.map((col) => {
              const isHighlight = activeHighlights.some((h) => h.key === col);
              return (
                <tr
                  key={col}
                  className={`border-b border-[#363A45]/50 last:border-0 hover:bg-[#2B2B43]/30 ${isHighlight ? "bg-[#2962FF]/5" : ""}`}
                >
                  <td className={`sticky left-0 bg-[#131722] px-2 py-1 z-10 whitespace-nowrap ${isHighlight ? "font-medium text-[#D1D4DC]" : "text-[#787B86]"}`}>
                    {col}
                  </td>
                  {periods.map((p, pi) => {
                    const val = items[col]?.[pi] ?? null;
                    return (
                      <td
                        key={p}
                        className="text-right px-2 py-1 font-mono tabular-nums whitespace-nowrap"
                      >
                        <span className={val != null ? (val >= 0 ? "text-[#D1D4DC]" : "text-[#F23645]") : "text-[#4C525E]"}>
                          {fmtValue(val)}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ── Trend chart ──────────────────────────────────────────────────── */}
      {chartOption && (
        <div className="shrink-0 h-[120px] border-t border-[#2B2B43]">
          <ReactECharts option={chartOption} style={{ height: "100%", width: "100%" }} notMerge />
        </div>
      )}
    </div>
  );
}
