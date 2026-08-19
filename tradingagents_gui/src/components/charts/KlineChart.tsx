import { useState } from "react";
import ReactECharts from "echarts-for-react";
import type { KlineData } from "../../lib/types";
import { CHART_COLORS } from "../../lib/echarts-theme";

interface Props {
  data: KlineData;
}

const MA_CONFIG: [string, keyof KlineData, string][] = [
  ["MA5", "ma5", "#F7B731"],
  ["MA10", "ma10", "#2962FF"],
  ["MA20", "ma20", "#9B59B6"],
  ["MA50", "ma50", "#26A69A"],
];

export default function KlineChart({ data }: Props) {
  const [visibleMa, setVisibleMa] = useState<Set<string>>(
    new Set(MA_CONFIG.map(([name]) => name))
  );

  const toggleMa = (name: string) => {
    setVisibleMa((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

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
        const lines = [
          `<b>${candle.axisValue}</b>`,
          `Open: ${open}`,
          `High: ${high}`,
          `Low: ${low}`,
          `Close: ${close}`,
          vol ? `Volume: ${vol.data?.toLocaleString()}` : "",
        ];
        // Add MA values to tooltip
        for (const [name, key, color] of MA_CONFIG) {
          if (!visibleMa.has(name)) continue;
          const values = data[key] as (number | null)[] | undefined;
          if (values) {
            const idx = candle.dataIndex;
            const val = values[idx];
            if (val != null) {
              lines.push(`<span style="color:${color}">●</span> ${name}: ${val.toFixed(2)}`);
            }
          }
        }
        return lines.filter(Boolean).join("<br/>");
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
      ...buildMaSeries(data, visibleMa),
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
    <div>
      {/* MA toggle buttons */}
      <div style={{ display: "flex", gap: 6, padding: "4px 16px", flexWrap: "wrap" }}>
        {MA_CONFIG.map(([name, , color]) => (
          <button
            key={name}
            onClick={() => toggleMa(name)}
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              border: `1px solid ${visibleMa.has(name) ? color : "#363A45"}`,
              background: visibleMa.has(name) ? `${color}22` : "transparent",
              color: visibleMa.has(name) ? color : "#787B86",
              fontSize: 11,
              cursor: "pointer",
              transition: "all 0.15s",
            }}
          >
            {name}
          </button>
        ))}
      </div>
      <ReactECharts
        option={option}
        style={{ height: 350, width: "100%" }}
        notMerge
      />
    </div>
  );
}

function buildMaSeries(data: KlineData, visibleMa: Set<string>) {
  return MA_CONFIG
    .filter(([name]) => visibleMa.has(name))
    .filter(([, key]) => {
      const values = data[key] as (number | null)[] | undefined;
      return values && values.length > 0;
    })
    .map(([name, key, color]) => ({
      name,
      type: "line" as const,
      data: data[key] as (number | null)[],
      smooth: true,
      lineStyle: { width: 1, color },
      symbol: "none",
    }));
}
