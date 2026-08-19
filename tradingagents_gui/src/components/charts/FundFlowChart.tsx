import ReactECharts from "echarts-for-react";
import type { FundFlowData } from "../../lib/types";
import { CHART_COLORS } from "../../lib/echarts-theme";

interface Props {
  data: FundFlowData;
}

export default function FundFlowChart({ data }: Props) {
  const option = {
    animation: true,
    animationDuration: 600,
    tooltip: {
      trigger: "axis",
      formatter: (params: any[]) => {
        const lines = params.map((p: any) => {
          const color = p.seriesName === "Northbound" ? CHART_COLORS.blue
            : p.seriesName === "Main Force" ? CHART_COLORS.orange
            : CHART_COLORS.gray;
          const val = typeof p.value === "number" ? p.value.toLocaleString() : p.value;
          return `<span style="color:${color}">●</span> ${p.seriesName}: ${val}`;
        });
        return `<b>${params[0]?.axisValue}</b><br/>${lines.join("<br/>")}`;
      },
    },
    legend: {
      data: ["Northbound", "Main Force", "Retail"],
      textStyle: { color: "#787B86", fontSize: 11 },
      top: 0,
    },
    grid: { left: 60, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: "category",
      data: data.dates,
      axisLine: { lineStyle: { color: "#363A45" } },
      axisLabel: { color: "#787B86", fontSize: 10, rotate: 30 },
    },
    yAxis: {
      axisLine: { lineStyle: { color: "#363A45" } },
      axisLabel: {
        color: "#787B86",
        fontSize: 10,
        formatter: (v: number) => {
          if (Math.abs(v) >= 1e8) return `${(v / 1e8).toFixed(1)}亿`;
          if (Math.abs(v) >= 1e4) return `${(v / 1e4).toFixed(1)}万`;
          return v.toString();
        },
      },
      splitLine: { lineStyle: { color: "#2A2E39" } },
    },
    series: [
      {
        name: "Northbound",
        type: "bar",
        stack: "flow",
        data: data.northbound,
        itemStyle: { color: CHART_COLORS.blue, borderRadius: [2, 2, 0, 0] },
      },
      {
        name: "Main Force",
        type: "bar",
        stack: "flow",
        data: data.mainForce,
        itemStyle: { color: CHART_COLORS.orange },
      },
      {
        name: "Retail",
        type: "bar",
        stack: "flow",
        data: data.retail,
        itemStyle: { color: CHART_COLORS.gray, borderRadius: [0, 0, 2, 2] },
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 250, width: "100%" }}
      notMerge
    />
  );
}
