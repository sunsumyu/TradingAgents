/**
 * ProfitForecastPanel — consensus EPS forecast + valuation metrics.
 *
 * Layout:
 * - Top readout: price / PE(TTM) / Forward PE / PEG
 * - ECharts bar chart: mean EPS per year, min-max range as error bars
 * - Analysts count per year
 */

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { ProfitForecastData } from "../../lib/types";

interface Props {
  data: ProfitForecastData;
  rawMd: string;
}

function fmt(v: number | null | undefined, digits = 2): string {
  return v != null ? v.toFixed(digits) : "—";
}

export default function ProfitForecastPanel({ data, rawMd }: Props) {
  const { years, current_price, pe_ttm, forward_pe, peg } = data;

  const option = useMemo(() => {
    if (!years.length) return null;

    const labels = years.map((y) => y.year);
    const means = years.map((y) => y.mean_eps ?? 0);
    const mins = years.map((y) => y.min_eps ?? null);
    const analysts = years.map((y) => y.analysts ?? 0);

    // Determine if any range data exists
    const hasRange = mins.some((m) => m != null);

    return {
      grid: { left: 48, right: 24, top: 24, bottom: 24 },
      tooltip: {
        trigger: "axis" as const,
        backgroundColor: "#1E222D",
        borderColor: "#363A45",
        textStyle: { color: "#D1D4DC", fontSize: 11 },
        formatter(params: any[]) {
          const idx = params[0]?.dataIndex ?? 0;
          const y = years[idx];
          if (!y) return "";
          const lines = [
            `<b>${y.year}</b>`,
            `一致预期 EPS: <b>${fmt(y.mean_eps)}</b>`,
          ];
          if (y.min_eps != null && y.max_eps != null) {
            lines.push(`区间: ${fmt(y.min_eps)} – ${fmt(y.max_eps)}`);
          }
          if (y.analysts != null) lines.push(`覆盖: ${y.analysts} 家`);
          return lines.join("<br/>");
        },
      },
      xAxis: {
        type: "category" as const,
        data: labels,
        axisLine: { lineStyle: { color: "#363A45" } },
        axisLabel: { color: "#787B86", fontSize: 11 },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value" as const,
        name: "EPS",
        nameTextStyle: { color: "#787B86", fontSize: 10, padding: [0, 0, 0, 30] },
        axisLine: { show: false },
        axisLabel: { color: "#787B86", fontSize: 10 },
        splitLine: { lineStyle: { color: "#2B2B43" } },
      },
      series: [
        // Mean EPS bars
        {
          type: "bar" as const,
          data: means,
          barWidth: 28,
          itemStyle: {
            color: {
              type: "linear" as const,
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: "#2962FF" },
                { offset: 1, color: "#2962FF66" },
              ],
            },
            borderRadius: [3, 3, 0, 0],
          },
          label: {
            show: true,
            position: "top" as const,
            formatter: "{c}",
            color: "#D1D4DC",
            fontSize: 10,
          },
        },
        // Min-max range (floating bar)
        ...(hasRange
          ? [
              {
                type: "bar" as const,
                data: years.map((y) => {
                  const lo = y.min_eps ?? y.mean_eps ?? 0;
                  const hi = y.max_eps ?? y.mean_eps ?? 0;
                  return [lo, hi];
                }),
                barWidth: 6,
                barGap: "-100%",
                itemStyle: { color: "rgba(255,152,0,0.25)" },
                tooltip: { show: false },
                silent: true,
              },
            ]
          : []),
        // Analysts count (scatter on secondary axis — invisible, just for tooltip)
        ...(analysts.some((a) => a > 0)
          ? [
              {
                type: "scatter" as const,
                data: analysts.map(() => [0, 0]), // invisible
                tooltip: { show: false },
                silent: true,
              },
            ]
          : []),
      ],
    };
  }, [years]);

  if (!years.length && !current_price && !pe_ttm) {
    return (
      <div className="h-full overflow-y-auto">
        {rawMd ? (
          <pre className="text-[11px] text-[#787B86] p-3 whitespace-pre-wrap leading-relaxed">
            {rawMd}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
            暂无数据
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      {/* Metrics readout */}
      <div className="flex flex-wrap gap-3 text-[11px]">
        {current_price != null && (
          <div>
            <span className="text-[#787B86]">现价 </span>
            <span className="text-[#D1D4DC] font-medium tabular-nums">{fmt(current_price)}</span>
          </div>
        )}
        {pe_ttm != null && (
          <div>
            <span className="text-[#787B86]">PE(TTM) </span>
            <span className="text-[#D1D4DC] font-medium tabular-nums">{fmt(pe_ttm)}</span>
          </div>
        )}
        {forward_pe != null && (
          <div>
            <span className="text-[#787B86]">Forward PE </span>
            <span className="text-[#2962FF] font-medium tabular-nums">{fmt(forward_pe)}</span>
          </div>
        )}
        {peg != null && (
          <div>
            <span className="text-[#787B86]">PEG </span>
            <span className={`font-medium tabular-nums ${peg < 1 ? "text-[#26A69A]" : peg <= 2 ? "text-[#D1D4DC]" : "text-[#F23645]"}`}>
              {fmt(peg)}
            </span>
          </div>
        )}
      </div>

      {/* EPS forecast chart */}
      {option && (
        <div className="bg-[#1E222D] rounded border border-[#363A45] p-2">
          <ReactECharts
            option={option}
            style={{ height: 160 }}
            opts={{ renderer: "svg" }}
            notMerge
          />
        </div>
      )}

      {/* Analysts coverage row */}
      {years.some((y) => y.analysts != null) && (
        <div className="flex gap-2 text-[10px]">
          {years.map((y) => (
            <div key={y.year} className="flex items-center gap-1 text-[#787B86]">
              <span className="text-[#D1D4DC]">{y.year}</span>
              <span>{y.analysts ?? "—"} 家覆盖</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
