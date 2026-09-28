import ReactECharts from "echarts-for-react";
import type { RsiData } from "../../lib/types";
import { CHART_COLORS } from "../../lib/echarts-theme";

interface Props {
  data: RsiData;
}

export default function RsiChart({ data }: Props) {
  const option = {
    animation: true,
    animationDuration: 800,
    tooltip: {
      trigger: "axis",
      formatter: (params: any[]) => {
        const p = params[0];
        return `<b>${p.axisValue}</b><br/>RSI: ${typeof p.value === "number" ? p.value.toFixed(2) : p.value}`;
      },
    },
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: "category",
      data: data.dates,
      axisLine: { lineStyle: { color: "#363A45" } },
      axisLabel: { color: "#787B86", fontSize: 10 },
    },
    yAxis: {
      min: 0,
      max: 100,
      axisLine: { lineStyle: { color: "#363A45" } },
      axisLabel: { color: "#787B86", fontSize: 10 },
      splitLine: { lineStyle: { color: "#2A2E39" } },
    },
    series: [
      {
        name: "RSI",
        type: "line",
        data: data.values,
        symbol: "none",
        lineStyle: { width: 2, color: CHART_COLORS.blue },
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(41,98,255,0.25)" },
              { offset: 1, color: "rgba(41,98,255,0.02)" },
            ],
          },
        },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { type: "dashed", width: 1 },
          data: [
            {
              yAxis: 70,
              lineStyle: { color: CHART_COLORS.red },
              label: { formatter: "70", color: CHART_COLORS.red, fontSize: 10 },
            },
            {
              yAxis: 30,
              lineStyle: { color: CHART_COLORS.green },
              label: { formatter: "30", color: CHART_COLORS.green, fontSize: 10 },
            },
          ],
        },
        markArea: {
          silent: true,
          data: [
            [
              { yAxis: 70, itemStyle: { color: "rgba(242,54,69,0.06)" } },
              { yAxis: 100 },
            ],
            [
              { yAxis: 0, itemStyle: { color: "rgba(8,153,129,0.06)" } },
              { yAxis: 30 },
            ],
          ],
        },
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 240, width: "100%" }}
      notMerge
    />
  );
}
