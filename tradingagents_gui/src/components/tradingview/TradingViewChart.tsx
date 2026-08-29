/**
 * TradingViewChart — Core chart using ECharts for candlestick + volume + MA overlays.
 *
 * ECharts works reliably in Tauri webview (confirmed by MACD/RSI panels).
 * We use ECharts with a dark TradingView theme for the main chart.
 */

import { useRef, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { KlineData } from "../../lib/types";
import type { CrosshairInfo, DrawingTool } from "./types";
import { COLORS } from "./chart-theme";
import DrawingOverlay from "./DrawingOverlay";

// ── Props ───────────────────────────────────────────────────────────────────

interface Props {
  data: KlineData | null;
  activeOverlays?: string[];
  activeTool?: DrawingTool;
  onCrosshairMove?: (info: CrosshairInfo | null) => void;
  /** MA series recomputed with adjustable params, keyed by overlay key (ma5/...). */
  maSeries?: Record<string, (number | null)[]>;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function TradingViewChart({
  data,
  activeOverlays = ["ma5", "ma10", "ma20"],
  activeTool = "crosshair",
  onCrosshairMove,
  maSeries,
}: Props) {
  const chartRef = useRef<any>(null);

  // Latest series data, readable from the updateAxisPointer event handler
  // without re-registering the handler on every option change.
  const datesRef = useRef<string[]>([]);
  const ohlcRef = useRef<KlineData["ohlc"]>([]);
  const volumesRef = useRef<number[]>([]);
  datesRef.current = data?.dates ?? [];
  ohlcRef.current = data?.ohlc ?? [];
  volumesRef.current = data?.volumes ?? [];

  const option = useMemo(() => {
    if (!data || !data.dates || data.dates.length === 0) return null;

    const dates = data.dates;
    const ohlc = data.ohlc;
    const volumes = data.volumes;

    // Candlestick data: [open, close, low, high]
    const candleData = ohlc.map((c) => [c[0], c[1], c[2], c[3]]);

    // Volume data with per-bar color
    const volumeData = ohlc.map((c, i) => ({
      value: volumes[i],
      itemStyle: {
        color: c[1] >= c[0] ? "rgba(8,153,129,0.5)" : "rgba(242,54,69,0.5)",
      },
    }));

    // MA overlay lines - prefer params-recomputed series over backend fields
    const overlayMap: Record<string, { data: (number | null)[]; color: string }> = {
      ma5: { data: maSeries?.ma5 ?? data.ma5 ?? [], color: COLORS.ma5 },
      ma10: { data: maSeries?.ma10 ?? data.ma10 ?? [], color: COLORS.ma10 },
      ma20: { data: maSeries?.ma20 ?? data.ma20 ?? [], color: COLORS.ma20 },
      ma50: { data: maSeries?.ma50 ?? data.ma50 ?? [], color: COLORS.ma50 },
      ema12: { data: data.ema12 ?? [], color: COLORS.ema12 },
      ema26: { data: data.ema26 ?? [], color: COLORS.ema26 },
    };

    const overlaySeries = activeOverlays
      .filter((k) => overlayMap[k]?.data?.length)
      .map((k) => ({
        name: k.toUpperCase(),
        type: "line" as const,
        data: overlayMap[k].data.map((v) => (v != null ? +v.toFixed(2) : null)),
        lineStyle: { width: 1, color: overlayMap[k].color },
        symbol: "none",
        itemStyle: { color: overlayMap[k].color },
        z: 5,
      }));

    // Latest price line
    const lastClose = ohlc[ohlc.length - 1][1];
    const prevClose = ohlc.length >= 2 ? ohlc[ohlc.length - 2][1] : lastClose;
    const priceColor = lastClose >= prevClose ? COLORS.up : COLORS.down;

    return {
      animation: false,
      backgroundColor: "#131722",
      grid: [
        { left: 60, right: 60, top: 10, bottom: "25%" },      // candle
        { left: 60, right: 60, top: "78%", bottom: 10 },       // volume
      ],
      xAxis: [
        {
          type: "category" as const,
          data: dates,
          gridIndex: 0,
          axisLine: { lineStyle: { color: "#2B2B43" } },
          axisLabel: { color: "#787B86", fontSize: 10 },
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
          axisLabel: { color: "#787B86", fontSize: 10 },
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
          axisPointer: {
            label: {
              show: true,
              color: "#FFFFFF",
              fontSize: 11,
              fontFamily: "monospace",
              padding: [4, 8],
              formatter: (params: any) => (params.value != null ? (+params.value).toFixed(2) : ""),
              backgroundColor: (params: any) => {
                const v = params.value;
                if (v == null || ohlc.length === 0) return COLORS.textMuted;
                return v >= lastClose ? COLORS.up : COLORS.down;
              },
            },
          },
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
          const candle = params.find((p: any) => p.seriesType === "candlestick");
          if (!candle) return "";
          const [open, close, low, high] = candle.data;
          const change = close - open;
          const pct = open !== 0 ? ((change / open) * 100).toFixed(2) : "0.00";
          const color = change >= 0 ? COLORS.up : COLORS.down;
          return `<div style="font-family:monospace;font-size:11px">
            <div style="color:${COLORS.textMuted}">${candle.axisValue}</div>
            <div style="color:${color}">O ${Number(open).toFixed(2)} H ${Number(high).toFixed(2)} L ${Number(low).toFixed(2)} C ${Number(close).toFixed(2)}</div>
            <div style="color:${color}">${change >= 0 ? "+" : ""}${change.toFixed(2)} (${change >= 0 ? "+" : ""}${pct}%)</div>
          </div>`;
        },
      },
      axisPointer: {
        link: [{ xAxisIndex: [0, 1] }],
      },
      dataZoom: [
        {
          type: "inside" as const,
          xAxisIndex: [0, 1],
          start: Math.max(0, 100 - (60 / dates.length) * 100),
          end: 100,
        },
        {
          type: "slider" as const,
          xAxisIndex: [0, 1],
          bottom: 5,
          height: 16,
          borderColor: "#2B2B43",
          backgroundColor: "#1E222D",
          dataBackground: {
            lineStyle: { color: "#2B2B43" },
            areaStyle: { color: "#1E222D" },
          },
          selectedDataBackground: {
            lineStyle: { color: "#2962FF" },
            areaStyle: { color: "rgba(41,98,255,0.1)" },
          },
          fillerColor: "rgba(41,98,255,0.1)",
          handleStyle: { color: "#2962FF", borderColor: "#2962FF" },
          textStyle: { color: "#787B86", fontSize: 10 },
          start: Math.max(0, 100 - (60 / dates.length) * 100),
          end: 100,
        },
      ],
      series: [
        // Candlestick
        {
          name: "K-line",
          type: "candlestick",
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: candleData,
          itemStyle: {
            color: COLORS.up,
            color0: COLORS.down,
            borderColor: COLORS.up,
            borderColor0: COLORS.down,
          },
          markLine: {
            silent: true,
            symbol: "none",
            data: [
              {
                yAxis: lastClose,
                lineStyle: { color: priceColor, width: 1, type: "dashed" as const },
                label: {
                  show: true,
                  position: "insideEndTop" as const,
                  formatter: lastClose.toFixed(2),
                  backgroundColor: priceColor,
                  color: "#fff",
                  padding: [2, 6],
                  fontSize: 11,
                },
              },
            ],
          },
        },
        // Volume
        {
          name: "Volume",
          type: "bar",
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumeData,
          barMaxWidth: 8,
        },
        // MA overlays
        ...overlaySeries,
      ],
    };
  }, [data, activeOverlays, maSeries]);

  // Crosshair info: read from the ECharts 'updateAxisPointer' global event,
  // which fires on every axis move (works for both daily and minute bars).
  const handleChartEvents = useMemo(() => ({
    globalout: () => onCrosshairMove?.(null),
    updateAxisPointer: (event: any) => {
      if (!onCrosshairMove) return;
      const axesInfo = event?.axesInfo;
      if (!axesInfo || axesInfo.length === 0) {
        onCrosshairMove(null);
        return;
      }
      // The candlestick series lives on the first x-axis; its dataIndex
      // identifies the hovered bar.
      const idx = axesInfo[0]?.value?.dataIndex ?? -1;
      if (idx < 0 || !ohlcRef.current.length) {
        onCrosshairMove(null);
        return;
      }
      const [open, close, low, high] = ohlcRef.current[idx] ?? [];
      if (close == null) {
        onCrosshairMove(null);
        return;
      }
      const prevClose =
        idx >= 1 && ohlcRef.current[idx - 1] ? ohlcRef.current[idx - 1][1] : close;
      onCrosshairMove({
        time: datesRef.current[idx] ?? "",
        open,
        high,
        low,
        close,
        volume: volumesRef.current[idx] ?? 0,
        change: close - prevClose,
        changePercent: prevClose !== 0 ? ((close - prevClose) / prevClose) * 100 : 0,
      });
    },
  }), [onCrosshairMove]);

  if (!option) {
    return (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#787B86", fontSize: 13, gap: 8 }}>
        <div style={{ fontSize: 15, color: "#D1D4DC" }}>暂无 K 线数据</div>
        <div style={{ fontSize: 12, maxWidth: 320, textAlign: "center", lineHeight: 1.5 }}>
          该标的可能不在数据源覆盖范围内，或网络连接异常。
          <br />请检查 ticker 是否正确，或稍后重试。
        </div>
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height: "100%", width: "100%" }}
        notMerge
        onEvents={handleChartEvents}
      />
      <DrawingOverlay activeTool={activeTool} resetKey={data?.dates[0]} />
    </div>
  );
}
