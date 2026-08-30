/**
 * Sub-indicator mini charts: WR, CCI, KDJ, MACD, RSI, Bollinger.
 *
 * All panels are derived from OHLC data on the client (see chart-utils.ts),
 * so no backend change is needed. Each uses the shared useCrosshairSync
 * hook for crosshair synchronization with the main chart.
 */

import { useEffect, useRef } from "react";
import ReactECharts from "echarts-for-react";
import type { KlineData, MacdData, RsiData, BollingerData } from "../../lib/types";
import { CHART_COLORS } from "../../lib/echarts-theme";
import { computeWR, computeCCI, computeExpma, computeXSChannel, computeTD9 } from "../../lib/chart-utils";
import type { SubIndicatorKey, IndicatorParams } from "../../lib/chart-utils";

/** Shared crosshair-sync wrapper used by both mini charts below. */
function useCrosshairSync(
  chartRef: React.RefObject<any>,
  dates: string[],
  crosshairTime?: string | null,
) {
  useEffect(() => {
    const inst = chartRef.current?.getEchartsInstance?.();
    if (!inst) return;

    if (crosshairTime) {
      const idx = dates.indexOf(crosshairTime);
      if (idx >= 0) {
        inst.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: idx });
      }
    } else {
      inst.dispatchAction({ type: "hideTip" });
    }
  }, [crosshairTime, dates, chartRef]);
}

export function WrMini({
  kline,
  period = 14,
  crosshairTime,
}: {
  kline: KlineData;
  period?: number;
  crosshairTime?: string | null;
}) {
  const chartRef = useRef<any>(null);
  useCrosshairSync(chartRef, kline.dates, crosshairTime);

  const values = computeWR(kline, period);

  const option = {
    animation: false,
    grid: { left: 50, right: 10, top: 20, bottom: 20 },
    tooltip: { trigger: "axis" as const },
    xAxis: {
      type: "category" as const,
      data: kline.dates,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { show: false },
    },
    yAxis: {
      min: 0,
      max: 100,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 9 },
      splitLine: { lineStyle: { color: "#1E222D" } },
    },
    series: [
      {
        name: `WR(${period})`,
        type: "line",
        data: values,
        symbol: "none",
        lineStyle: { width: 1.2, color: CHART_COLORS.yellow },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { type: "dashed" as const, width: 0.5 },
          data: [
            { yAxis: 80, lineStyle: { color: CHART_COLORS.red } },
            { yAxis: 20, lineStyle: { color: CHART_COLORS.green } },
          ],
        },
      },
    ],
  };

  return (
    <div className="h-full">
      <ReactECharts ref={chartRef} option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}

export function CciMini({
  kline,
  period = 20,
  crosshairTime,
}: {
  kline: KlineData;
  period?: number;
  crosshairTime?: string | null;
}) {
  const chartRef = useRef<any>(null);
  useCrosshairSync(chartRef, kline.dates, crosshairTime);

  const values = computeCCI(kline, period);

  const option = {
    animation: false,
    grid: { left: 50, right: 10, top: 20, bottom: 20 },
    tooltip: { trigger: "axis" as const },
    xAxis: {
      type: "category" as const,
      data: kline.dates,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { show: false },
    },
    yAxis: {
      scale: true,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 9 },
      splitLine: { lineStyle: { color: "#1E222D" } },
    },
    series: [
      {
        name: `CCI(${period})`,
        type: "line",
        data: values,
        symbol: "none",
        lineStyle: { width: 1.2, color: CHART_COLORS.purple },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { type: "dashed" as const, width: 0.5 },
          data: [{ yAxis: 0, lineStyle: { color: "#4C525E" } }],
        },
      },
    ],
  };

  return (
    <div className="h-full">
      <ReactECharts ref={chartRef} option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}

// ── KDJ ──────────────────────────────────────────────────────────────────────

export function KdjMini({
  data,
  crosshairTime,
}: {
  data: KlineData;
  crosshairTime?: string | null;
}) {
  const chartRef = useRef<any>(null);
  useCrosshairSync(chartRef, data.dates, crosshairTime);

  const option = {
    animation: false,
    grid: { left: 50, right: 10, top: 20, bottom: 20 },
    tooltip: { trigger: "axis" as const },
    xAxis: {
      type: "category" as const,
      data: data.dates,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { show: false },
    },
    yAxis: {
      min: 0,
      max: 100,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 9 },
      splitLine: { lineStyle: { color: "#1E222D" } },
    },
    series: [
      {
        name: "K",
        type: "line",
        data: data.kdj_k ?? [],
        lineStyle: { width: 1.2, color: CHART_COLORS.blue },
        symbol: "none",
      },
      {
        name: "D",
        type: "line",
        data: data.kdj_d ?? [],
        lineStyle: { width: 1.2, color: CHART_COLORS.yellow },
        symbol: "none",
      },
      {
        name: "J",
        type: "line",
        data: data.kdj_j ?? [],
        lineStyle: { width: 1.2, color: CHART_COLORS.purple },
        symbol: "none",
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { type: "dashed" as const, width: 1 },
          data: [
            { yAxis: 80, lineStyle: { color: CHART_COLORS.red }, label: { formatter: "80", color: CHART_COLORS.red, fontSize: 9 } },
            { yAxis: 20, lineStyle: { color: CHART_COLORS.green }, label: { formatter: "20", color: CHART_COLORS.green, fontSize: 9 } },
          ],
        },
      },
    ],
  };

  return (
    <div className="h-full">
      <ReactECharts ref={chartRef} option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}

// ── MACD ─────────────────────────────────────────────────────────────────────

export function MacdMini({
  data,
  crosshairTime,
}: {
  data: MacdData;
  crosshairTime?: string | null;
}) {
  const chartRef = useRef<any>(null);
  useCrosshairSync(chartRef, data.dates, crosshairTime);

  const option = {
    animation: false,
    grid: { left: 50, right: 10, top: 20, bottom: 20 },
    tooltip: { trigger: "axis" as const },
    xAxis: {
      type: "category" as const,
      data: data.dates,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { show: false },
    },
    yAxis: {
      scale: true,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 9 },
      splitLine: { lineStyle: { color: "#1E222D" } },
    },
    series: [
      { name: "MACD", type: "line", data: data.macd, lineStyle: { width: 1, color: CHART_COLORS.blue }, symbol: "none" },
      { name: "Signal", type: "line", data: data.signal, lineStyle: { width: 1, color: CHART_COLORS.yellow }, symbol: "none" },
      {
        name: "Histogram",
        type: "bar",
        data: data.histogram.map((v) => ({
          value: v,
          itemStyle: { color: v >= 0 ? "rgba(8,153,129,0.6)" : "rgba(242,54,69,0.6)" },
        })),
      },
    ],
  };

  return (
    <div className="h-full">
      <ReactECharts ref={chartRef} option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}

// ── RSI ──────────────────────────────────────────────────────────────────────

export function RsiMini({
  data,
  crosshairTime,
}: {
  data: RsiData;
  crosshairTime?: string | null;
}) {
  const chartRef = useRef<any>(null);
  useCrosshairSync(chartRef, data.dates, crosshairTime);

  const option = {
    animation: false,
    grid: { left: 50, right: 10, top: 20, bottom: 20 },
    tooltip: { trigger: "axis" as const },
    xAxis: {
      type: "category" as const,
      data: data.dates,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { show: false },
    },
    yAxis: {
      min: 0,
      max: 100,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 9 },
      splitLine: { lineStyle: { color: "#1E222D" } },
    },
    series: [
      {
        name: "RSI",
        type: "line",
        data: data.values,
        symbol: "none",
        lineStyle: { width: 1.5, color: CHART_COLORS.blue },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { type: "dashed" as const, width: 0.5 },
          data: [
            { yAxis: 70, lineStyle: { color: CHART_COLORS.red } },
            { yAxis: 30, lineStyle: { color: CHART_COLORS.green } },
          ],
        },
      },
    ],
  };

  return (
    <div className="h-full">
      <ReactECharts ref={chartRef} option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}

// ── Bollinger ────────────────────────────────────────────────────────────────

export function BollingerMini({
  data,
  crosshairTime,
}: {
  data: BollingerData;
  crosshairTime?: string | null;
}) {
  const chartRef = useRef<any>(null);
  useCrosshairSync(chartRef, data.dates, crosshairTime);

  const option = {
    animation: false,
    grid: { left: 50, right: 10, top: 20, bottom: 20 },
    tooltip: { trigger: "axis" as const },
    xAxis: {
      type: "category" as const,
      data: data.dates,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { show: false },
    },
    yAxis: {
      scale: true,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 9 },
      splitLine: { lineStyle: { color: "#1E222D" } },
    },
    series: [
      { name: "Upper", type: "line", data: data.upper, lineStyle: { width: 0.8, color: CHART_COLORS.red, type: "dashed" as const }, symbol: "none" },
      { name: "Middle", type: "line", data: data.middle, lineStyle: { width: 1, color: CHART_COLORS.blue }, symbol: "none" },
      { name: "Lower", type: "line", data: data.lower, lineStyle: { width: 0.8, color: CHART_COLORS.green, type: "dashed" as const }, symbol: "none" },
    ],
  };

  return (
    <div className="h-full">
      <ReactECharts ref={chartRef} option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}

// ── EXPMA ───────────────────────────────────────────────────────────────────

export function ExpmaMini({
  kline,
  shortPeriod = 12,
  longPeriod = 50,
  crosshairTime,
}: {
  kline: KlineData;
  shortPeriod?: number;
  longPeriod?: number;
  crosshairTime?: string | null;
}) {
  const chartRef = useRef<any>(null);
  useCrosshairSync(chartRef, kline.dates, crosshairTime);

  const closes = kline.ohlc.map((r) => r[1]);
  const { short, long } = computeExpma(closes, shortPeriod, longPeriod);

  const option = {
    animation: false,
    grid: { left: 50, right: 10, top: 20, bottom: 20 },
    tooltip: { trigger: "axis" as const },
    xAxis: {
      type: "category" as const,
      data: kline.dates,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { show: false },
    },
    yAxis: {
      scale: true,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 9 },
      splitLine: { lineStyle: { color: "#1E222D" } },
    },
    series: [
      { name: "EXPMA-S", type: "line", data: short, symbol: "none", lineStyle: { width: 1, color: "#2962FF" } },
      { name: "EXPMA-L", type: "line", data: long, symbol: "none", lineStyle: { width: 1, color: "#FF6D00" } },
    ],
  };

  return (
    <div className="h-full">
      <ReactECharts ref={chartRef} option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}

// ── XS Channel (薛斯通道) ──────────────────────────────────────────────────

export function XSChannelMini({
  kline,
  longPeriod = 100,
  shortPeriod = 10,
  k = 11,
  crosshairTime,
}: {
  kline: KlineData;
  longPeriod?: number;
  shortPeriod?: number;
  k?: number;
  crosshairTime?: string | null;
}) {
  const chartRef = useRef<any>(null);
  useCrosshairSync(chartRef, kline.dates, crosshairTime);

  const { upper, lower } = computeXSChannel(kline, longPeriod, shortPeriod, k);

  const option = {
    animation: false,
    grid: { left: 50, right: 10, top: 20, bottom: 20 },
    tooltip: { trigger: "axis" as const },
    xAxis: {
      type: "category" as const,
      data: kline.dates,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { show: false },
    },
    yAxis: {
      scale: true,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 9 },
      splitLine: { lineStyle: { color: "#1E222D" } },
    },
    series: [
      { name: "上轨", type: "line", data: upper, symbol: "none", lineStyle: { width: 1, color: CHART_COLORS.red, type: "dashed" as const } },
      { name: "下轨", type: "line", data: lower, symbol: "none", lineStyle: { width: 1, color: CHART_COLORS.green, type: "dashed" as const } },
    ],
  };

  return (
    <div className="h-full">
      <ReactECharts ref={chartRef} option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}

// ── TD9 (神奇九转) ─────────────────────────────────────────────────────────

export function TD9Mini({
  kline,
  crosshairTime,
}: {
  kline: KlineData;
  crosshairTime?: string | null;
}) {
  const chartRef = useRef<any>(null);
  useCrosshairSync(chartRef, kline.dates, crosshairTime);

  const { buyCount, sellCount, buySignals, sellSignals } = computeTD9(kline);

  const option = {
    animation: false,
    grid: { left: 50, right: 10, top: 20, bottom: 20 },
    tooltip: { trigger: "axis" as const },
    xAxis: {
      type: "category" as const,
      data: kline.dates,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { show: false },
    },
    yAxis: {
      type: "value" as const,
      min: 0,
      max: 10,
      interval: 3,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 9 },
      splitLine: { lineStyle: { color: "#1E222D" } },
    },
    series: [
      {
        name: "买入",
        type: "line",
        data: buyCount,
        symbol: "none",
        lineStyle: { width: 1.5, color: "#2962FF" },
        markLine: buySignals.length > 0 ? {
          silent: true,
          symbol: "none",
          data: buySignals.map((idx) => ({
            xAxis: idx,
            lineStyle: { color: "#2962FF", type: "solid" as const, width: 1 },
            label: { show: true, formatter: "9", color: "#2962FF", fontSize: 10 },
          })),
        } : undefined,
      },
      {
        name: "卖出",
        type: "line",
        data: sellCount,
        symbol: "none",
        lineStyle: { width: 1.5, color: "#F23645" },
        markLine: sellSignals.length > 0 ? {
          silent: true,
          symbol: "none",
          data: sellSignals.map((idx) => ({
            xAxis: idx,
            lineStyle: { color: "#F23645", type: "solid" as const, width: 1 },
            label: { show: true, formatter: "9", color: "#F23645", fontSize: 10 },
          })),
        } : undefined,
      },
    ],
  };

  return (
    <div className="h-full">
      <ReactECharts ref={chartRef} option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}

// ── SubIndicatorPanel (dispatcher) ───────────────────────────────────────────

export function SubIndicatorPanel({
  indicator,
  kline,
  macd,
  rsi,
  bollinger,
  crosshairTime,
  params,
}: {
  indicator: SubIndicatorKey;
  kline: KlineData | null;
  macd?: MacdData | null;
  rsi?: RsiData | null;
  bollinger?: BollingerData | null;
  crosshairTime?: string | null;
  params?: IndicatorParams;
}) {
  switch (indicator) {
    case "MACD":
      return macd ? <MacdMini data={macd} crosshairTime={crosshairTime} /> : null;
    case "RSI":
      return rsi ? <RsiMini data={rsi} crosshairTime={crosshairTime} /> : null;
    case "Bollinger":
      return bollinger ? <BollingerMini data={bollinger} crosshairTime={crosshairTime} /> : null;
    case "KDJ":
      return kline?.kdj_k?.length ? <KdjMini data={kline} crosshairTime={crosshairTime} /> : null;
    case "WR":
      return kline?.ohlc?.length ? <WrMini kline={kline} crosshairTime={crosshairTime} /> : null;
    case "CCI":
      return kline?.ohlc?.length ? <CciMini kline={kline} crosshairTime={crosshairTime} /> : null;
    case "EXPMA":
      return kline?.ohlc?.length
        ? <ExpmaMini kline={kline} shortPeriod={params?.expma.short} longPeriod={params?.expma.long} crosshairTime={crosshairTime} />
        : null;
    case "XSChannel":
      return kline?.ohlc?.length
        ? <XSChannelMini kline={kline} longPeriod={params?.xsChannel.longPeriod} shortPeriod={params?.xsChannel.shortPeriod} k={params?.xsChannel.k} crosshairTime={crosshairTime} />
        : null;
    case "TD9":
      return kline?.ohlc?.length ? <TD9Mini kline={kline} crosshairTime={crosshairTime} /> : null;
  }
}
