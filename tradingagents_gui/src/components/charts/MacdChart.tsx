import ReactECharts from "echarts-for-react";
import type { MacdData } from "../../lib/types";
import { CHART_COLORS } from "../../lib/echarts-theme";

interface Props {
  data: MacdData;
}

export default function MacdChart({ data }: Props) {
  const option = {
    animation: true,
    animationDuration: 600,
    tooltip: {
      trigger: "axis",
      formatter: (params: any[]) => {
        const lines = params.map((p: any) => {
          const color = p.seriesName === "MACD" ? CHART_COLORS.blue
            : p.seriesName === "Signal" ? CHART_COLORS.yellow
            : undefined;
          const prefix = color ? `<span style="color:${color}">●</span> ` : "";
          return `${prefix}${p.seriesName}: ${typeof p.value === "number" ? p.value.toFixed(4) : p.value}`;
        });
        return `<b>${params[0]?.axisValue}</b><br/>${lines.join("<br/>")}`;
      },
    },
    legend: {
      data: ["MACD", "Signal", "Histogram"],
      textStyle: { color: "#787B86", fontSize: 11 },
      top: 0,
    },
    grid: { left: 60, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: "category",
      data: data.dates,
      axisLine: { lineStyle: { color: "#363A45" } },
      axisLabel: { color: "#787B86", fontSize: 10 },
    },
    yAxis: {
      scale: true,
      axisLine: { lineStyle: { color: "#363A45" } },
      axisLabel: { color: "#787B86", fontSize: 10 },
      splitLine: { lineStyle: { color: "#2A2E39" } },
    },
    series: [
      {
        name: "MACD",
        type: "line",
        data: data.macd,
        lineStyle: { width: 1.5, color: CHART_COLORS.blue },
        symbol: "none",
      },
      {
        name: "Signal",
        type: "line",
        data: data.signal,
        lineStyle: { width: 1.5, color: CHART_COLORS.yellow },
        symbol: "none",
      },
      {
        name: "Histogram",
        type: "bar",
        data: data.histogram.map((v) => ({
          value: v,
          itemStyle: {
            color: v >= 0
              ? "rgba(8,153,129,0.7)"
              : "rgba(242,54,69,0.7)",
          },
        })),
        animationDelay: (idx: number) => idx * 30,
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 200, width: "100%" }}
      notMerge
    />
  );
}
