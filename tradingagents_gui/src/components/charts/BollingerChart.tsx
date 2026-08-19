import ReactECharts from "echarts-for-react";
import type { BollingerData } from "../../lib/types";
import { CHART_COLORS } from "../../lib/echarts-theme";

interface Props {
  data: BollingerData;
}

export default function BollingerChart({ data }: Props) {
  const option = {
    animation: true,
    animationDuration: 800,
    tooltip: {
      trigger: "axis",
      formatter: (params: any[]) => {
        const lines = params.map((p: any) => {
          const color =
            p.seriesName === "Upper"
              ? CHART_COLORS.red
              : p.seriesName === "Lower"
                ? CHART_COLORS.green
                : p.seriesName === "Close"
                  ? "#D1D4DC"
                  : CHART_COLORS.blue;
          return `<span style="color:${color}">●</span> ${p.seriesName}: ${typeof p.value === "number" ? p.value.toFixed(2) : p.value}`;
        });
        return `<b>${params[0]?.axisValue}</b><br/>${lines.join("<br/>")}`;
      },
    },
    legend: {
      data: ["Upper", "Middle", "Lower", "Close"],
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
        name: "Upper",
        type: "line",
        data: data.upper,
        lineStyle: { width: 1, color: CHART_COLORS.red, type: "dashed" },
        symbol: "none",
        markArea: {
          silent: true,
          data: data.dates.map((d, i) => [
            {
              xAxis: d,
              yAxis: data.lower[i],
              itemStyle: { color: "rgba(41,98,255,0.08)" },
            },
            { xAxis: d, yAxis: data.upper[i] },
          ]),
        },
      },
      {
        name: "Middle",
        type: "line",
        data: data.middle,
        lineStyle: { width: 1.5, color: CHART_COLORS.blue },
        symbol: "none",
      },
      {
        name: "Lower",
        type: "line",
        data: data.lower,
        lineStyle: { width: 1, color: CHART_COLORS.green, type: "dashed" },
        symbol: "none",
      },
      {
        name: "Close",
        type: "line",
        data: data.close,
        lineStyle: { width: 2, color: "#D1D4DC" },
        symbol: "circle",
        symbolSize: 4,
        itemStyle: { color: "#D1D4DC" },
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
