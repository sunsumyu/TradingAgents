/**
 * IndexChartsRow — 三大指数分时图（ECharts line chart × 3）。
 *
 * Shows 上证指数 / 深证成指 / 创业板指 intraday trends
 * with price line + average price line + volume bars.
 */

import { useEffect, useRef } from "react";
import type { IndexData } from "../../lib/types";

interface Props {
  indices: Record<string, IndexData>;
}

const INDEX_ORDER = ["000001", "399001", "399006"];
const INDEX_COLORS: Record<string, string> = {
  "000001": "#F23645",  // 上证 红
  "399001": "#2962FF",  // 深证 蓝
  "399006": "#26A69A",  // 创业板 绿
};

function IndexChart({ code, data }: { code: string; data: IndexData }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.trends?.length) return;
    let chart: any;

    import("echarts").then(({ init }) => {
      chart = init(ref.current!);
      const times = data.trends.map((t: { time: string }) => t.time);
      const prices = data.trends.map((t: { price: number }) => t.price);
      const avgPrices = data.trends.map((t: { avg_price: number }) => t.avg_price);
      const volumes = data.trends.map((t: { volume: number }) => t.volume);

      const color = INDEX_COLORS[code] || "#D1D4DC";
      const preClose = data.pre_close || prices[0];

      chart.setOption({
        animation: false,
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "cross" },
          formatter: (params: any[]) => {
            const p = params[0];
            return `${p.axisValue}<br/>${p.seriesName}: ${p.value.toFixed(2)} (${((p.value - preClose) / preClose * 100).toFixed(2)}%)`;
          },
        },
        grid: { left: 45, right: 10, top: 25, bottom: 20 },
        xAxis: {
          type: "category",
          data: times,
          axisLabel: { color: "#787B86", fontSize: 9, interval: 59 },
          axisLine: { lineStyle: { color: "#1E222D" } },
        },
        yAxis: [
          {
            type: "value",
            scale: true,
            axisLabel: { color: "#787B86", fontSize: 9, formatter: (v: number) => v.toFixed(0) },
            splitLine: { lineStyle: { color: "#1E222D" } },
          },
          {
            type: "value",
            scale: true,
            axisLabel: { show: false },
            splitLine: { show: false },
          },
        ],
        series: [
          {
            name: data.name,
            type: "line",
            data: prices,
            showSymbol: false,
            lineStyle: { color, width: 1.5 },
            areaStyle: {
              color: {
                type: "linear", x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0, color: color + "30" },
                  { offset: 1, color: color + "05" },
                ],
              },
            },
            yAxisIndex: 0,
          },
          {
            name: "均价",
            type: "line",
            data: avgPrices,
            showSymbol: false,
            lineStyle: { color: "#FFB74D", width: 1, type: "dashed" },
            yAxisIndex: 0,
          },
          {
            name: "成交量",
            type: "bar",
            data: volumes,
            barWidth: "60%",
            itemStyle: { color: "#1E222D" },
            yAxisIndex: 1,
          },
        ],
      });
    });

    return () => { chart?.dispose(); };
  }, [code, data]);

  const changePct = data.change_pct ?? 0;
  const changeColor = changePct > 0 ? "#F23645" : changePct < 0 ? "#26A69A" : "#787B86";

  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-baseline gap-2 mb-1 px-1">
        <span className="text-[12px] font-medium text-[#D1D4DC]">{data.name}</span>
        <span className="text-[14px] font-bold tabular-nums" style={{ color: changeColor }}>
          {data.price.toFixed(2)}
        </span>
        <span className="text-[11px] tabular-nums" style={{ color: changeColor }}>
          {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
        </span>
      </div>
      <div ref={ref} className="w-full h-[140px]" />
    </div>
  );
}

export default function IndexChartsRow({ indices }: Props) {
  const validIndices = INDEX_ORDER.filter((code) => indices[code]);

  if (validIndices.length === 0) {
    return (
      <div className="flex items-center justify-center h-[160px] text-[#787B86] text-xs">
        暂无指数数据
      </div>
    );
  }

  return (
    <div className="flex gap-2 p-2 border-b border-[#1E222D] bg-[#131722]">
      {validIndices.map((code) => (
        <IndexChart key={code} code={code} data={indices[code]} />
      ))}
    </div>
  );
}
