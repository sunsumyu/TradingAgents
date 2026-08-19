import ReactECharts from "echarts-for-react";
import type { KlineData } from "../../lib/types";
import { CHART_COLORS } from "../../lib/echarts-theme";

interface Props {
  data: KlineData;
}

export default function KlineChart({ data }: Props) {
  const option = {
    animation: true,
    animationDuration: 800,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params: any[]) => {
        const candle = params.find((p: any) => p.seriesType === "candlestick");
        if (!candle) return "";
        const [open, close, low, high] = candle.data;
        const vol = params.find((p: any) => p.seriesName === "Volume");
        return [
          `<b>${candle.axisValue}</b>`,
          `Open: ${open}`,
          `High: ${high}`,
          `Low: ${low}`,
          `Close: ${close}`,
          vol ? `Volume: ${vol.data?.toLocaleString()}` : "",
        ]
          .filter(Boolean)
          .join("<br/>");
      },
    },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { left: 60, right: 20, top: 30, height: "55%" },
      { left: 60, right: 20, top: "72%", height: "18%" },
    ],
    xAxis: [
      {
        type: "category",
        data: data.dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "#363A45" } },
        axisLabel: { color: "#787B86", fontSize: 10 },
        min: "dataMin",
        max: "dataMax",
      },
      {
        type: "category",
        gridIndex: 1,
        data: data.dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "#363A45" } },
        axisLabel: { show: false },
        min: "dataMin",
        max: "dataMax",
      },
    ],
    yAxis: [
      {
        scale: true,
        splitArea: { show: false },
        axisLine: { lineStyle: { color: "#363A45" } },
        axisLabel: { color: "#787B86", fontSize: 10 },
        splitLine: { lineStyle: { color: "#2A2E39" } },
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 60, end: 100 },
      {
        type: "slider",
        xAxisIndex: [0, 1],
        bottom: 5,
        height: 18,
        borderColor: "#363A45",
        fillerColor: "rgba(41,98,255,0.15)",
        handleStyle: { color: "#2962FF" },
        textStyle: { color: "#787B86" },
        start: 60,
        end: 100,
      },
    ],
    series: [
      {
        name: "K-line",
        type: "candlestick",
        data: data.ohlc,
        itemStyle: {
          color: CHART_COLORS.green,
          color0: CHART_COLORS.red,
          borderColor: CHART_COLORS.green,
          borderColor0: CHART_COLORS.red,
        },
      },
      ...buildMaSeries(data),
      {
        name: "Volume",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: data.volumes,
        itemStyle: {
          color: (params: any) => {
            const idx = params.dataIndex;
            const [open, close] = data.ohlc[idx] || [0, 0];
            return close >= open
              ? "rgba(8,153,129,0.4)"
              : "rgba(242,54,69,0.4)";
          },
        },
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 350, width: "100%" }}
      notMerge
    />
  );
}

function buildMaSeries(data: KlineData) {
  const maConfig: [string, (number | null)[] | undefined, string][] = [
    ["MA5", data.ma5, "#F7B731"],
    ["MA10", data.ma10, "#2962FF"],
    ["MA20", data.ma20, "#9B59B6"],
    ["MA50", data.ma50, "#26A69A"],
  ];

  return maConfig
    .filter(([, values]) => values && values.length > 0)
    .map(([name, values, color]) => ({
      name,
      type: "line" as const,
      data: values,
      smooth: true,
      lineStyle: { width: 1, color },
      symbol: "none",
    }));
}
