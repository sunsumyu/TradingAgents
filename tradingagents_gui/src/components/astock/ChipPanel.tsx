/**
 * ChipPanel — Horizontal chip distribution chart (筹码分布).
 *
 * Renders a horizontal bar chart (ECharts):
 *   Y-axis: price bins
 *   X-axis: chip % per bin
 *   Red bars = chips below current price (获利盘)
 *   Green bars = chips above current price (套牢盘)
 *   Dashed line at current price
 *   Stats readout: profit ratio, avg cost, peak price
 *
 * Falls back to raw_md rendering if structured data is empty.
 */

import { useMemo, useRef } from "react";
import ReactECharts from "echarts-for-react";
import type { ChipDistributionData } from "../../lib/types";

interface Props {
  data: ChipDistributionData;
  rawMd: string;
}

const UP_COLOR = "rgba(242,54,69,0.7)";    // 套牢盘 (above current = trapped = red)
const DOWN_COLOR = "rgba(8,153,129,0.7)";  // 获利盘 (below current = profit = green)
const CURRENT_PRICE_COLOR = "#FFD700";     // current price marker

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-1 text-xs">
      <span className="text-[#787B86]">{label}</span>
      <span className="text-[#D1D4DC] font-mono">{value}</span>
    </div>
  );
}

export default function ChipPanel({ data, rawMd }: Props) {
  const chartRef = useRef<any>(null);

  // Build ECharts option
  const option = useMemo(() => {
    const levels = data.price_levels ?? [];
    if (levels.length === 0) return null;

    const currentPrice = data.current_price ?? 0;
    const prices = levels.map((l) => l.price.toFixed(2));

    // Color each bar: green if price < current (profit), red if above (trapped)
    const barData = levels.map((l) => ({
      value: l.ratio,
      itemStyle: {
        color: l.price < currentPrice ? DOWN_COLOR : UP_COLOR,
        borderRadius: [0, 2, 2, 0],
      },
    }));

    // Mark lines: current price, peak price, avg cost
    const markLines: any[] = [];
    if (data.current_price != null) {
      markLines.push({
        yAxis: currentPrice.toFixed(2),
        lineStyle: { color: CURRENT_PRICE_COLOR, width: 1.5, type: "dashed" },
        label: { show: true, formatter: `当前 ${currentPrice.toFixed(2)}`, color: CURRENT_PRICE_COLOR, fontSize: 10 },
      });
    }
    if (data.peak_price != null && Math.abs(data.peak_price - currentPrice) / currentPrice > 0.005) {
      markLines.push({
        yAxis: data.peak_price.toFixed(2),
        lineStyle: { color: "#9B59B6", width: 1, type: "dotted" },
        label: { show: true, formatter: `峰值 ${data.peak_price.toFixed(2)}`, color: "#9B59B6", fontSize: 9 },
      });
    }
    if (data.avg_cost != null && Math.abs(data.avg_cost - currentPrice) / currentPrice > 0.005) {
      markLines.push({
        yAxis: data.avg_cost.toFixed(2),
        lineStyle: { color: "#3498DB", width: 1, type: "dotted" },
        label: { show: true, formatter: `均成本 ${data.avg_cost.toFixed(2)}`, color: "#3498DB", fontSize: 9 },
      });
    }

    return {
      animation: false,
      grid: { left: 70, right: 30, top: 15, bottom: 25 },
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "shadow" as const },
        formatter: (params: any[]) => {
          const p = params[0];
          if (!p) return "";
          return `<b>${p.name}</b><br/>筹码占比: ${p.value?.toFixed(1)}%`;
        },
      },
      xAxis: {
        type: "value" as const,
        axisLine: { lineStyle: { color: "#2B2B43" } },
        axisLabel: { color: "#787B86", fontSize: 9, formatter: "{value}%" },
        splitLine: { lineStyle: { color: "#1E222D", type: "dashed" as const } },
      },
      yAxis: {
        type: "category" as const,
        data: prices,
        inverse: false, // lowest price at bottom
        axisLine: { lineStyle: { color: "#2B2B43" } },
        axisLabel: { color: "#787B86", fontSize: 9 },
      },
      series: [
        {
          name: "筹码占比",
          type: "bar",
          data: barData,
          barMaxWidth: 12,
          markLine: {
            silent: true,
            symbol: "none",
            data: markLines,
          },
        },
      ],
    };
  }, [data]);

  // Structured data empty → fallback to raw_md
  if (!option || data.price_levels?.length === 0) {
    return (
      <div className="h-full overflow-y-auto">
        {rawMd ? (
          <pre className="text-[11px] text-[#787B86] p-3 whitespace-pre-wrap leading-relaxed">
            {rawMd}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
            无筹码分布数据
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Stats readout */}
      <div className="flex items-center gap-4 px-3 py-1.5 border-b border-[#2B2B43]">
        {data.profit_ratio != null && (
          <StatItem label="获利盘" value={`${data.profit_ratio.toFixed(1)}%`} />
        )}
        {data.avg_cost != null && (
          <StatItem label="平均成本" value={data.avg_cost.toFixed(2)} />
        )}
        {data.peak_price != null && (
          <StatItem label="筹码峰值" value={data.peak_price.toFixed(2)} />
        )}
        {data.current_price != null && (
          <StatItem label="当前价" value={data.current_price.toFixed(2)} />
        )}
      </div>

      {/* Horizontal bar chart */}
      <div className="flex-1 min-h-0">
        <ReactECharts
          ref={chartRef}
          option={option}
          style={{ height: "100%", width: "100%" }}
          notMerge
        />
      </div>
    </div>
  );
}
