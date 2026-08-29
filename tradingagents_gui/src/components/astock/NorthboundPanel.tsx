/**
 * NorthboundPanel — Northbound capital flow (沪深股通/北向资金) panel.
 *
 * Top readout: today's HGT + SGT net inflow (亿) and total, colored by sign.
 * Main chart: stacked bar chart of daily close history (HGT red / SGT blue),
 * plus a total line. Falls back to raw_md when no structured history exists.
 */

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { NorthboundData } from "../../lib/types";

interface Props {
  data: NorthboundData;
  rawMd: string;
}

const HGT_COLOR = "#F23645"; // 沪股通
const SGT_COLOR = "#2962FF"; // 深股通

function fmtYi(v: number | null | undefined): string {
  if (v == null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}亿`;
}

function Readout({ label, value }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-1 text-xs">
      <span className="text-[#787B86]">{label}</span>
      <span className="text-[#D1D4DC] font-mono">{value}</span>
    </div>
  );
}

export default function NorthboundPanel({ data, rawMd }: Props) {
  const history = data.history ?? [];

  const option = useMemo(() => {
    if (history.length === 0) return null;

    const dates = history.map((d) => d.date);
    const hgtVals = history.map((d) => d.hgt);
    const sgtVals = history.map((d) => d.sgt);
    const totals = history.map((d) => d.hgt + d.sgt);

    return {
      animation: false,
      grid: { left: 60, right: 20, top: 25, bottom: 25 },
      tooltip: {
        trigger: "axis" as const,
        formatter: (params: any[]) => {
          if (!params?.length) return "";
          const date = params[0].axisValue;
          const lines = [`<b>${date}</b>`];
          for (const p of params) {
            lines.push(`${p.marker}${p.seriesName}: ${Number(p.value).toFixed(2)}亿`);
          }
          return lines.join("<br/>");
        },
      },
      legend: {
        data: ["沪股通", "深股通", "合计"],
        textStyle: { color: "#787B86", fontSize: 10 },
        top: 0,
        right: 10,
      },
      xAxis: {
        type: "category" as const,
        data: dates,
        axisLine: { lineStyle: { color: "#2B2B43" } },
        axisLabel: { color: "#787B86", fontSize: 9 },
      },
      yAxis: {
        type: "value" as const,
        axisLine: { lineStyle: { color: "#2B2B43" } },
        axisLabel: { color: "#787B86", fontSize: 9, formatter: "{value}亿" },
        splitLine: { lineStyle: { color: "#1E222D", type: "dashed" as const } },
      },
      series: [
        {
          name: "沪股通",
          type: "bar",
          stack: "flow",
          data: hgtVals,
          itemStyle: { color: HGT_COLOR },
          barMaxWidth: 18,
        },
        {
          name: "深股通",
          type: "bar",
          stack: "flow",
          data: sgtVals,
          itemStyle: { color: SGT_COLOR },
          barMaxWidth: 18,
        },
        {
          name: "合计",
          type: "line",
          data: totals,
          symbol: "circle",
          symbolSize: 4,
          lineStyle: { width: 1.5, color: "#FFD700" },
          itemStyle: { color: "#FFD700" },
        },
      ],
    };
  }, [history]);

  const hasToday = data.hgt_net_inflow != null || data.sgt_net_inflow != null;
  const total =
    (data.hgt_net_inflow ?? 0) + (data.sgt_net_inflow ?? 0);

  if (!option && !hasToday && !rawMd) {
    return (
      <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
        暂无北向资金数据
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Today's readout */}
      {hasToday && (
        <div className="flex items-center gap-4 px-3 py-1.5 border-b border-[#2B2B43]">
          <Readout label="沪股通" value={fmtYi(data.hgt_net_inflow)} />
          <Readout label="深股通" value={fmtYi(data.sgt_net_inflow)} />
          <Readout label="合计" value={fmtYi(data.hgt_net_inflow != null && data.sgt_net_inflow != null ? total : null)} />
        </div>
      )}

      {/* History time series */}
      {option ? (
        <div className="flex-1 min-h-0">
          <ReactECharts option={option} style={{ height: "100%", width: "100%" }} notMerge />
        </div>
      ) : rawMd ? (
        <div className="flex-1 overflow-y-auto">
          <pre className="text-[11px] text-[#787B86] p-3 whitespace-pre-wrap leading-relaxed">
            {rawMd}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
