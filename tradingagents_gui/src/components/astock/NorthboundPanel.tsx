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
import { formatDateShort, formatDateDisplay } from "../../lib/dateFormat";
import { useLanguage } from "../../lib/useLanguage";
import { withTheme } from "../shared/chartTheme";

interface Props {
  data?: NorthboundData;
  rawMd: string;
}

const HGT_COLOR = "#ef4444"; // 沪股通 (red)
const SGT_COLOR = "#3b82f6"; // 深股通 (blue)

function fmtYi(v: number | null | undefined): string {
  if (v == null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}亿`;
}

function Readout({ label, value }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-text-secondary">{label}</span>
      <span className="text-text-primary font-mono font-semibold">{value}</span>
    </div>
  );
}

// Parse realtime tick data from raw markdown
function parseRealtimeTicks(rawMd: string): Array<{ time: string; hgt: number; sgt: number }> {
  const ticks: Array<{ time: string; hgt: number; sgt: number }> = [];
  const lines = rawMd.split("\n");
  for (const line of lines) {
    const match = line.match(/^\s*(\d{2}:\d{2}):\s*HGT=(-?[\d.]+)\s*SGT=(-?[\d.]+)/);
    if (match) {
      ticks.push({
        time: match[1],
        hgt: parseFloat(match[2]),
        sgt: parseFloat(match[3]),
      });
    }
  }
  return ticks;
}

export default function NorthboundPanel({ data, rawMd }: Props) {
  const lang = useLanguage();
  const history = data?.history ?? [];
  const realtimeTicks = useMemo(() => parseRealtimeTicks(rawMd), [rawMd]);

  const option = useMemo(() => {
    if (history.length === 0) return null;

    const dates = history.map((d) => formatDateShort(d.date, lang));
    const hgtVals = history.map((d) => d.hgt);
    const sgtVals = history.map((d) => d.sgt);
    const totals = history.map((d) => d.hgt + d.sgt);

    return withTheme({
      grid: { left: 50, right: 16, top: 28, bottom: 28 },
      tooltip: {
        trigger: "axis" as const,
        formatter: (params: any[]) => {
          if (!params?.length) return "";
          const rawDate = history[params[0].dataIndex]?.date ?? params[0].axisValue;
          const date = formatDateDisplay(rawDate, lang);
          const lines = [`<b>${date}</b>`];
          for (const p of params) {
            lines.push(`${p.marker}${p.seriesName}: ${Number(p.value).toFixed(2)}亿`);
          }
          return lines.join("<br/>");
        },
      },
      legend: {
        data: ["沪股通", "深股通", "合计"],
        top: 0,
        right: 10,
      },
      xAxis: {
        type: "category" as const,
        data: dates,
      },
      yAxis: {
        type: "value" as const,
        axisLabel: { formatter: "{value}亿" },
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
          lineStyle: { width: 1.5, color: "#f59e0b" },
          itemStyle: { color: "#f59e0b" },
        },
      ],
    });
  }, [history]);

  const hasToday = data?.hgt_net_inflow != null || data?.sgt_net_inflow != null;
  const total =
    (data?.hgt_net_inflow ?? 0) + (data?.sgt_net_inflow ?? 0);

  if (!option && !hasToday && !rawMd) {
    return (
      <div className="flex items-center justify-center h-full text-text-secondary text-xs">
        暂无北向资金数据
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Today's readout */}
      {hasToday && (
        <div className="flex items-center gap-6 px-4 py-2 border-b border-line">
          <Readout label="沪股通" value={fmtYi(data.hgt_net_inflow)} />
          <Readout label="深股通" value={fmtYi(data.sgt_net_inflow)} />
          <Readout label="合计" value={fmtYi(data.hgt_net_inflow != null && data.sgt_net_inflow != null ? total : null)} />
        </div>
      )}

      {/* History time series chart */}
      {option ? (
        <div className="flex-1 min-h-0">
          <ReactECharts option={option} style={{ height: "100%", width: "100%" }} notMerge />
        </div>
      ) : realtimeTicks.length > 0 ? (
        /* Realtime tick table */
        <div className="flex-1 overflow-y-auto p-4">
          <div className="text-[11px] text-text-secondary mb-3 font-medium">
            实时逐笔数据（累计净买入，亿元）
          </div>
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-line">
                <th className="text-left py-2 text-text-secondary font-medium">时间</th>
                <th className="text-right py-2 text-text-secondary font-medium">沪股通 (HGT)</th>
                <th className="text-right py-2 text-text-secondary font-medium">深股通 (SGT)</th>
                <th className="text-right py-2 text-text-secondary font-medium">合计</th>
              </tr>
            </thead>
            <tbody>
              {realtimeTicks.map((tick, i) => {
                const total = tick.hgt + tick.sgt;
                const totalColor = total >= 0 ? "text-up" : "text-down";
                return (
                  <tr key={i} className="border-b border-line/50 hover:bg-bg-hover/50">
                    <td className="py-1.5 text-text-primary font-mono">{tick.time}</td>
                    <td className={`py-1.5 text-right font-mono ${tick.hgt >= 0 ? "text-up" : "text-down"}`}>
                      {tick.hgt.toFixed(2)}
                    </td>
                    <td className={`py-1.5 text-right font-mono ${tick.sgt >= 0 ? "text-up" : "text-down"}`}>
                      {tick.sgt.toFixed(2)}
                    </td>
                    <td className={`py-1.5 text-right font-mono font-semibold ${totalColor}`}>
                      {total.toFixed(2)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : rawMd ? (
        /* Fallback: raw markdown */
        <div className="flex-1 overflow-y-auto p-4">
          <pre className="text-[12px] text-text-secondary whitespace-pre-wrap leading-relaxed font-mono">
            {rawMd}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
