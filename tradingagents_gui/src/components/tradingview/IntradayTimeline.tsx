/**
 * IntradayTimeline — ECharts intraday price line chart with VWAP overlay,
 * volume bars, and previous-close reference line.
 *
 * Uses the same dark TradingView palette as TradingViewChart.
 */

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { KlineData } from "../../lib/types";
import { computeVwap } from "../../lib/chart-utils";
import { COLORS } from "./chart-theme";

interface Props {
  data: KlineData | null;
  /** Previous session close — used for the horizontal reference line. */
  prevClose?: number | null;
}

export default function IntradayTimeline({ data, prevClose }: Props) {
  const option = useMemo(() => {
    if (!data || !data.dates || data.dates.length === 0) return null;

    const dates = data.dates;
    const ohlc = data.ohlc;
    const volumes = data.volumes;

    // Close prices for the price line
    const closes = ohlc.map((c) => c[1]);

    // VWAP computation
    const vwap = computeVwap(closes, volumes);

    // Per-bar price color (above/below prevClose for coloring)
    const refPrice = prevClose ?? closes[0];
    const priceColor =
      closes[closes.length - 1] >= refPrice ? COLORS.up : COLORS.down;

    // Volume bar data with color
    const volumeData = ohlc.map((c, i) => ({
      value: volumes[i],
      itemStyle: {
        color: c[1] >= c[0] ? "rgba(8,153,129,0.45)" : "rgba(242,54,69,0.45)",
      },
    }));

    // Mark line for prev close
    const markLineData =
      prevClose != null
        ? [
            {
              yAxis: prevClose,
              lineStyle: { color: "#787B86", width: 1, type: "dashed" as const },
              label: {
                show: true,
                position: "insideEndTop" as const,
                formatter: `昨收 ${prevClose.toFixed(2)}`,
                backgroundColor: "#787B86",
                color: "#fff",
                padding: [2, 6],
                fontSize: 10,
              },
            },
          ]
        : [];

    return {
      animation: false,
      backgroundColor: "#131722",
      grid: [
        { left: 60, right: 60, top: 10, bottom: "25%" },   // price + VWAP
        { left: 60, right: 60, top: "78%", bottom: 10 },    // volume
      ],
      xAxis: [
        {
          type: "category" as const,
          data: dates,
          gridIndex: 0,
          axisLine: { lineStyle: { color: "#2B2B43" } },
          axisLabel: { color: "#787B86", fontSize: 10, showMaxLabel: false },
          axisTick: { show: false },
          splitLine: { show: false },
          axisPointer: {
            label: {
              show: true,
              backgroundColor: "#2962FF",
              color: "#FFFFFF",
              fontSize: 10,
              padding: [3, 6],
            },
          },
        },
        {
          type: "category" as const,
          data: dates,
          gridIndex: 1,
          axisLine: { lineStyle: { color: "#2B2B43" } },
          axisLabel: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          type: "value" as const,
          gridIndex: 0,
          scale: true,
          axisLine: { lineStyle: { color: "#2B2B43" } },
          axisLabel: { color: "#787B86", fontSize: 10 },
          splitLine: { lineStyle: { color: "#1E222D" } },
          position: "right" as const,
        },
        {
          type: "value" as const,
          gridIndex: 1,
          scale: true,
          axisLine: { lineStyle: { color: "#2B2B43" } },
          axisLabel: { color: "#787B86", fontSize: 9 },
          splitLine: { show: false },
          position: "right" as const,
        },
      ],
      tooltip: {
        trigger: "axis" as const,
        axisPointer: {
          type: "cross" as const,
          crossStyle: { color: "#787B86" },
        },
        backgroundColor: "#1E222D",
        borderColor: "#2B2B43",
        textStyle: { color: "#D1D4DC", fontSize: 11 },
        formatter: (params: any[]) => {
          if (!params || params.length === 0) return "";
          const priceParam = params.find((p: any) => p.seriesType === "line" && p.seriesName === "价格");
          const vwapParam = params.find((p: any) => p.seriesName === "VWAP");
          const volParam = params.find((p: any) => p.seriesType === "bar");
          if (!priceParam) return "";

          const close = priceParam.value as number;
          const time = priceParam.axisValue;
          const ref = refPrice ?? close;
          const change = close - ref;
          const pct = ref !== 0 ? ((change / ref) * 100).toFixed(2) : "0.00";
          const color = change >= 0 ? COLORS.up : COLORS.down;

          let html = `<div style="font-family:monospace;font-size:11px">
            <div style="color:${COLORS.textMuted}">${time}</div>
            <div style="color:${color}">价格 ${close.toFixed(2)} (${change >= 0 ? "+" : ""}${change.toFixed(2)}, ${change >= 0 ? "+" : ""}${pct}%)</div>`;
          if (vwapParam?.value != null) {
            html += `<div style="color:#E9A741">VWAP ${Number(vwapParam.value).toFixed(2)}</div>`;
          }
          if (volParam?.value != null) {
            html += `<div style="color:${COLORS.textMuted}">量 ${Number(volParam.value).toLocaleString()}</div>`;
          }
          html += `</div>`;
          return html;
        },
      },
      axisPointer: {
        link: [{ xAxisIndex: [0, 1] }],
      },
      dataZoom: [
        {
          type: "inside" as const,
          xAxisIndex: [0, 1],
          start: 0,
          end: 100,
        },
      ],
      series: [
        // Price line (area fill)
        {
          name: "价格",
          type: "line",
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: closes,
          showSymbol: false,
          lineStyle: { color: priceColor, width: 1.5 },
          areaStyle: {
            color: {
              type: "linear" as const,
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: priceColor === COLORS.up ? "rgba(8,153,129,0.25)" : "rgba(242,54,69,0.25)" },
                { offset: 1, color: "rgba(0,0,0,0)" },
              ],
            },
          },
          markLine: markLineData.length > 0 ? { silent: true, symbol: "none", data: markLineData } : undefined,
        },
        // VWAP line
        {
          name: "VWAP",
          type: "line",
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: vwap.map((v) => (v != null ? +v.toFixed(2) : null)),
          showSymbol: false,
          lineStyle: { color: "#E9A741", width: 1, type: "dashed" as const },
        },
        // Volume bars
        {
          name: "成交量",
          type: "bar",
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumeData,
          barMaxWidth: 6,
        },
      ],
    };
  }, [data, prevClose]);

  if (!option) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          color: "#787B86",
          fontSize: 13,
          gap: 8,
        }}
      >
        <div style={{ fontSize: 15, color: "#D1D4DC" }}>暂无分时数据</div>
        <div style={{ fontSize: 12, maxWidth: 320, textAlign: "center", lineHeight: 1.5 }}>
          请选择分钟级别周期查看分时图。
        </div>
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ReactECharts option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}
