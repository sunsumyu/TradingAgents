/**
 * MiniChart — 个股分时图（点击股票后显示）。
 */

import { useEffect, useRef } from "react";

interface Props {
  ticker: string | null;
  name?: string;
  trends: Array<{ time: string; price: number; avg_price: number; volume: number }>;
  preClose?: number;
}

export default function MiniChart({ ticker, name, trends, preClose }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || !ticker || trends.length === 0) return;
    let chart: any;

    import("echarts").then(({ init }) => {
      chart = init(chartRef.current!);
      const times = trends.map((t) => t.time);
      const prices = trends.map((t) => t.price);
      const avgPrices = trends.map((t) => t.avg_price);
      const volumes = trends.map((t) => t.volume);

      const basePrice = preClose ?? prices[0];
      const changePct = ((prices[prices.length - 1] - basePrice) / basePrice * 100).toFixed(2);
      const color = Number(changePct) >= 0 ? "#F23645" : "#26A69A";

      chart.setOption({
        title: {
          text: `${ticker} ${name ?? ""}`,
          subtext: `${prices[prices.length - 1].toFixed(2)} (${changePct}%)`,
          textStyle: { color: "#D1D4DC", fontSize: 12 },
          subtextStyle: { color, fontSize: 11 },
          left: 8, top: 4,
        },
        grid: { left: 45, right: 10, top: 35, bottom: 20 },
        xAxis: {
          type: "category",
          data: times,
          axisLabel: { color: "#4C525E", fontSize: 9, interval: Math.floor(times.length / 4) },
          axisLine: { lineStyle: { color: "#1E222D" } },
        },
        yAxis: [
          {
            type: "value",
            scale: true,
            axisLabel: { color: "#787B86", fontSize: 9, formatter: (v: number) => v.toFixed(0) },
            splitLine: { lineStyle: { color: "#1E222D", type: "dashed" } },
          },
          {
            type: "value",
            scale: true,
            position: "right",
            axisLabel: { color: "#4C525E", fontSize: 9, formatter: (v: number) => (v / 1000).toFixed(0) + "K" },
            splitLine: { show: false },
          },
        ],
        series: [
          {
            type: "line",
            data: prices,
            smooth: false,
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
          },
          {
            type: "line",
            data: avgPrices,
            smooth: false,
            showSymbol: false,
            lineStyle: { color: "#FFA726", width: 1, type: "dashed" },
          },
          {
            type: "bar",
            yAxisIndex: 1,
            data: volumes,
            itemStyle: { color: "#4C525E40" },
            barWidth: "60%",
          },
        ],
        tooltip: {
          trigger: "axis",
          backgroundColor: "#1E222D",
          borderColor: "#2A2E39",
          textStyle: { color: "#D1D4DC", fontSize: 11 },
        },
      });
    });

    return () => { chart?.dispose(); };
  }, [ticker, trends, preClose, name]);

  if (!ticker) {
    return (
      <div className="h-full flex items-center justify-center text-[#4C525E] text-xs">
        点击股票查看分时图
      </div>
    );
  }

  return <div ref={chartRef} className="w-full h-full min-h-[200px]" />;
}
