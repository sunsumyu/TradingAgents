/**
 * IndustryComparisonPanel — Horizontal bar chart of industry rankings
 * by change percentage, with a scrollable table fallback.
 *
 * Layout: readout bar + ECharts horizontal bar chart + table.
 */

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { IndustryComparisonData } from "../../lib/types";

interface Props {
  data: IndustryComparisonData;
  rawMd: string;
}

export default function IndustryComparisonPanel({ data, rawMd }: Props) {
  const { rankings } = data;

  // ── Readout stats ─────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    if (!rankings.length) return null;
    const sorted = [...rankings].sort(
      (a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0),
    );
    return {
      count: rankings.length,
      best: sorted[0],
      worst: sorted[sorted.length - 1],
    };
  }, [rankings]);

  // ── ECharts option (horizontal bar chart) ─────────────────────────────────
  const chartOption = useMemo(() => {
    if (!rankings.length) return null;

    // Show top 15 by absolute change (most impactful)
    const shown = [...rankings]
      .sort((a, b) => Math.abs(b.change_pct ?? 0) - Math.abs(a.change_pct ?? 0))
      .slice(0, 15)
      .reverse(); // bottom to top

    const names = shown.map((r) => r.name);
    const values = shown.map((r) => r.change_pct ?? 0);

    return {
      animation: false,
      backgroundColor: "transparent",
      grid: { left: 80, right: 40, top: 8, bottom: 8 },
      xAxis: {
        type: "value" as const,
        axisLine: { lineStyle: { color: "#2B2B43" } },
        axisLabel: { color: "#787B86", fontSize: 9, formatter: "{value}%" },
        splitLine: { lineStyle: { color: "#1E222D" } },
      },
      yAxis: {
        type: "category" as const,
        data: names,
        axisLine: { lineStyle: { color: "#2B2B43" } },
        axisLabel: { color: "#D1D4DC", fontSize: 10, width: 70, overflow: "truncate" },
        axisTick: { show: false },
      },
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "shadow" as const },
        backgroundColor: "#1E222D",
        borderColor: "#2B2B43",
        textStyle: { color: "#D1D4DC", fontSize: 10 },
      },
      series: [
        {
          type: "bar",
          data: values.map((v) => ({
            value: v,
            itemStyle: {
              color: v >= 0 ? "rgba(8,153,129,0.7)" : "rgba(242,54,69,0.7)",
              borderRadius: v >= 0 ? [0, 2, 2, 0] : [2, 0, 0, 2],
            },
          })),
          barMaxWidth: 12,
          label: {
            show: true,
            position: "right" as const,
            formatter: (p: any) => `${Number(p.value).toFixed(2)}%`,
            color: "#787B86",
            fontSize: 9,
          },
        },
      ],
    };
  }, [rankings]);

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!rankings.length) {
    return (
      <div className="h-full overflow-y-auto">
        {rawMd ? (
          <pre className="text-[11px] text-[#787B86] p-3 whitespace-pre-wrap leading-relaxed">
            {rawMd}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
            暂无行业数据
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* ── Readout bar ──────────────────────────────────────────────────── */}
      <div className="flex items-center gap-4 px-3 py-1.5 border-b border-[#2B2B43] text-[11px] shrink-0">
        <span className="text-[#787B86]">
          {stats?.count} 个行业
        </span>
        {stats?.best && (
          <span className="text-[#089981]">
            最强: {stats.best.name} {stats.best.change_pct != null ? `+${stats.best.change_pct.toFixed(2)}%` : ""}
          </span>
        )}
        {stats?.worst && (
          <span className="text-[#F23645]">
            最弱: {stats.worst.name} {stats.worst.change_pct != null ? `${stats.worst.change_pct.toFixed(2)}%` : ""}
          </span>
        )}
      </div>

      {/* ── Chart ─────────────────────────────────────────────────────────── */}
      {chartOption && (
        <div className="shrink-0 h-[160px]">
          <ReactECharts option={chartOption} style={{ height: "100%", width: "100%" }} notMerge />
        </div>
      )}

      {/* ── Scrollable table ─────────────────────────────────────────────── */}
      <div className="overflow-y-auto flex-1 min-h-0">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-[10px] text-[#4C525E] border-b border-[#2B2B43]">
              <th className="text-center px-2 py-1.5 font-medium w-8">#</th>
              <th className="text-left px-2 py-1.5 font-medium">行业</th>
              <th className="text-right px-2 py-1.5 font-medium">涨跌幅</th>
              <th className="text-right px-2 py-1.5 font-medium">↑</th>
              <th className="text-right px-2 py-1.5 font-medium">↓</th>
              <th className="text-left px-2 py-1.5 font-medium">领涨股</th>
            </tr>
          </thead>
          <tbody>
            {rankings.map((r) => (
              <tr key={r.rank} className="border-b border-[#363A45]/50 last:border-0 hover:bg-[#2B2B43]/30">
                <td className="text-center px-2 py-1 text-[#4C525E]">{r.rank}</td>
                <td className="text-left px-2 py-1 text-[#D1D4DC]">{r.name}</td>
                <td className={`text-right px-2 py-1 font-mono tabular-nums ${(r.change_pct ?? 0) >= 0 ? "text-[#089981]" : "text-[#F23645]"}`}>
                  {r.change_pct != null ? `${r.change_pct >= 0 ? "+" : ""}${r.change_pct.toFixed(2)}%` : "—"}
                </td>
                <td className="text-right px-2 py-1 font-mono text-[#089981]">{r.up_count ?? "—"}</td>
                <td className="text-right px-2 py-1 font-mono text-[#F23645]">{r.down_count ?? "—"}</td>
                <td className="text-left px-2 py-1 text-[#787B86]">{r.leader}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
