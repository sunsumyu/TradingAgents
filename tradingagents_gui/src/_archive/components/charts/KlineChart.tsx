import { useState, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { KlineData } from "../../lib/types";
import { CHART_COLORS } from "../../lib/echarts-theme";
import {
  OVERLAY_INDICATORS as OVERLAY_CONFIG,
  getLatestIndicatorValue,
  buildOverlaySeries,
  type IndicatorKey,
} from "../../lib/chart-utils";

interface Props {
  data: KlineData;
}

export default function KlineChart({ data }: Props) {
  const [visibleOverlays, setVisibleOverlays] = useState<Set<IndicatorKey>>(
    new Set(["MA5", "MA10", "MA20", "MA50"]),
  );
  const [showKdj, setShowKdj] = useState(true);

  const toggleOverlay = (name: IndicatorKey) => {
    setVisibleOverlays((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  // Current values for the indicator parameter bar
  const latestIdx = data.ohlc.length - 1;
  const latestOhlc = data.ohlc[latestIdx] ?? [0, 0, 0, 0];
  const [open, close, low, high] = latestOhlc;
  const priceChange = latestIdx > 0
    ? close - (data.ohlc[latestIdx - 1]?.[1] ?? close)
    : 0;
  const priceChangePct = latestIdx > 0 && data.ohlc[latestIdx - 1]?.[1]
    ? (priceChange / data.ohlc[latestIdx - 1][1]) * 100
    : 0;

  const getLatestValue = (field: keyof KlineData): string =>
    getLatestIndicatorValue(data, field);

  // KDJ latest values
  const kdjK = getLatestValue("kdj_k");
  const kdjD = getLatestValue("kdj_d");
  const kdjJ = getLatestValue("kdj_j");

  const option = useMemo(() => {
    const baseGrid: any[] = [
      { left: 55, right: 20, top: 20, height: "48%" },   // K-line
      { left: 55, right: 20, top: "70%", height: "12%" }, // Volume
    ];
    const baseXaxis: any[] = [
      {
        type: "category" as const,
        data: data.dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "#363A45" } },
        axisLabel: { color: "#787B86", fontSize: 10 },
        min: "dataMin" as const,
        max: "dataMax" as const,
      },
      {
        type: "category" as const,
        gridIndex: 1,
        data: data.dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "#363A45" } },
        axisLabel: { show: false },
        min: "dataMin" as const,
        max: "dataMax" as const,
      },
    ];
    const baseYaxis: any[] = [
      {
        scale: true,
        splitArea: { show: false },
        axisLine: { lineStyle: { color: "#363A45" } },
        axisLabel: { show: true, color: "#787B86", fontSize: 10 },
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
    ];

    let grids = [...baseGrid];
    let xAxes = [...baseXaxis];
    let yAxes = [...baseYaxis];

    // Add KDJ grid if enabled
    if (showKdj && data.kdj_k && data.kdj_d) {
      grids.push({ left: 55, right: 20, top: "84%", height: "12%" });
      xAxes.push({
        type: "category" as const,
        gridIndex: 2,
        data: data.dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "#363A45" } },
        axisLabel: { show: false },
        min: "dataMin" as const,
        max: "dataMax" as const,
      });
      yAxes.push({
        scale: true,
        gridIndex: 2,
        splitNumber: 2,
        axisLabel: { show: true, color: "#787B86", fontSize: 9 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "#2A2E39" } },
      });
    }

    // Build series
    const series: any[] = [
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
      ...buildOverlaySeries(data, visibleOverlays),
      {
        name: "Volume",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: data.volumes,
        itemStyle: {
          color: (params: any) => {
            const idx = params.dataIndex;
            const [o, c] = data.ohlc[idx] || [0, 0];
            return c >= o ? "rgba(8,153,129,0.4)" : "rgba(242,54,69,0.4)";
          },
        },
      },
    ];

    // Add KDJ series
    if (showKdj && data.kdj_k && data.kdj_d && data.kdj_j) {
      const kdjGridIdx = 2;
      series.push(
        {
          name: "K",
          type: "line",
          xAxisIndex: kdjGridIdx,
          yAxisIndex: kdjGridIdx,
          data: data.kdj_k,
          lineStyle: { width: 1.2, color: "#2962FF" },
          symbol: "none",
        },
        {
          name: "D",
          type: "line",
          xAxisIndex: kdjGridIdx,
          yAxisIndex: kdjGridIdx,
          data: data.kdj_d,
          lineStyle: { width: 1.2, color: "#F7B731" },
          symbol: "none",
        },
        {
          name: "J",
          type: "line",
          xAxisIndex: kdjGridIdx,
          yAxisIndex: kdjGridIdx,
          data: data.kdj_j,
          lineStyle: { width: 1.2, color: "#E040FB" },
          symbol: "none",
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: { type: "dashed", width: 1 },
            data: [
              { yAxis: 80, lineStyle: { color: CHART_COLORS.red }, label: { formatter: "80", color: CHART_COLORS.red, fontSize: 9 } },
              { yAxis: 20, lineStyle: { color: CHART_COLORS.green }, label: { formatter: "20", color: CHART_COLORS.green, fontSize: 9 } },
            ],
          },
        },
      );
    }

    return {
      animation: true,
      animationDuration: 800,
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross", link: [{ xAxisIndex: "all" }] },
        backgroundColor: "rgba(30,34,45,0.96)",
        borderColor: "#363A45",
        textStyle: { color: "#D1D4DC", fontSize: 12 },
        formatter: (params: any[]) => {
          const candle = params.find((p: any) => p.seriesName === "K-line");
          if (!candle) return "";
          const [o, c, l, h] = candle.data;
          const vol = params.find((p: any) => p.seriesName === "Volume");
          const chg = o > 0 ? ((c - o) / o * 100) : 0;
          const chgColor = c >= o ? CHART_COLORS.green : CHART_COLORS.red;
          const lines = [
            `<b style="font-size:13px">${candle.axisValue}</b>`,
            `<span style="color:${chgColor}">●</span> O <b>${o.toFixed(2)}</b>  H <b>${h.toFixed(2)}</b>  L <b>${l.toFixed(2)}</b>  C <b style="color:${chgColor}">${c.toFixed(2)}</b>  <span style="color:${chgColor}">${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%</span>`,
          ];
          if (vol) {
            lines.push(`Vol: <b>${vol.data?.toLocaleString() ?? ""}</b>`);
          }
          // Overlay values
          for (const cfg of OVERLAY_CONFIG) {
            if (!visibleOverlays.has(cfg.key)) continue;
            const arr = data[cfg.field] as (number | null)[] | undefined;
            if (arr) {
              const val = arr[candle.dataIndex];
              if (val != null) {
                lines.push(`<span style="color:${cfg.color}">●</span> ${cfg.key}: <b>${val.toFixed(2)}</b>`);
              }
            }
          }
          // KDJ values
          if (showKdj && data.kdj_k) {
            const kVal = data.kdj_k[candle.dataIndex];
            const dVal = data.kdj_d?.[candle.dataIndex];
            const jVal = data.kdj_j?.[candle.dataIndex];
            if (kVal != null) {
              lines.push(`<span style="color:#2962FF">●</span> K: <b>${kVal.toFixed(1)}</b>  D: <b>${dVal?.toFixed(1) ?? "—"}</b>  J: <b>${jVal?.toFixed(1) ?? "—"}</b>`);
            }
          }
          return lines.join("<br/>");
        },
      },
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      grid: grids,
      xAxis: xAxes,
      yAxis: yAxes,
      dataZoom: [
        { type: "inside", xAxisIndex: Array.from({ length: grids.length }, (_, i) => i), start: 50, end: 100 },
        {
          type: "slider",
          xAxisIndex: Array.from({ length: grids.length }, (_, i) => i),
          bottom: 4,
          height: 16,
          borderColor: "#363A45",
          fillerColor: "rgba(41,98,255,0.15)",
          handleStyle: { color: "#2962FF" },
          textStyle: { color: "#787B86", fontSize: 10 },
          start: 50,
          end: 100,
        },
      ],
      series,
    };
  }, [data, visibleOverlays, showKdj]);

  return (
    <div>
      {/* ── Indicator Parameter Bar (TradingView-style) ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "4px 16px",
          flexWrap: "wrap",
          borderBottom: "1px solid #2A2E39",
          marginBottom: 4,
        }}
      >
        {/* Price info */}
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span style={{ fontSize: 12, color: "#787B86" }}>O</span>
          <span style={{ fontSize: 12, color: "#D1D4DC", fontWeight: 600 }}>{open.toFixed(2)}</span>
          <span style={{ fontSize: 12, color: "#787B86" }}>H</span>
          <span style={{ fontSize: 12, color: "#D1D4DC", fontWeight: 600 }}>{high.toFixed(2)}</span>
          <span style={{ fontSize: 12, color: "#787B86" }}>L</span>
          <span style={{ fontSize: 12, color: "#D1D4DC", fontWeight: 600 }}>{low.toFixed(2)}</span>
          <span style={{ fontSize: 12, color: "#787B86" }}>C</span>
          <span style={{
            fontSize: 12,
            color: priceChange >= 0 ? CHART_COLORS.green : CHART_COLORS.red,
            fontWeight: 600,
          }}>
            {close.toFixed(2)}
          </span>
          <span style={{
            fontSize: 11,
            color: priceChange >= 0 ? CHART_COLORS.green : CHART_COLORS.red,
          }}>
            {priceChange >= 0 ? "+" : ""}{priceChangePct.toFixed(2)}%
          </span>
        </div>

        {/* Divider */}
        <div style={{ width: 1, height: 14, background: "#363A45" }} />

        {/* MA / EMA toggle buttons */}
        {OVERLAY_CONFIG.map(({ key, color }) => {
          const arr = data[OVERLAY_CONFIG.find(c => c.key === key)!.field] as (number | null)[] | undefined;
          const val = arr?.[arr.length - 1];
          return (
            <button
              key={key}
              onClick={() => toggleOverlay(key)}
              style={{
                padding: "1px 6px",
                borderRadius: 3,
                border: `1px solid ${visibleOverlays.has(key) ? color : "transparent"}`,
                background: "transparent",
                color: visibleOverlays.has(key) ? color : "#555",
                fontSize: 11,
                cursor: "pointer",
                transition: "all 0.15s",
                whiteSpace: "nowrap",
              }}
            >
              {key} <span style={{ opacity: 0.8 }}>{val != null ? val.toFixed(2) : "—"}</span>
            </button>
          );
        })}

        {/* Divider */}
        <div style={{ width: 1, height: 14, background: "#363A45" }} />

        {/* KDJ toggle */}
        <button
          onClick={() => setShowKdj((v) => !v)}
          style={{
            padding: "1px 6px",
            borderRadius: 3,
            border: `1px solid ${showKdj ? "#00BCD4" : "transparent"}`,
            background: "transparent",
            color: showKdj ? "#00BCD4" : "#555",
            fontSize: 11,
            cursor: "pointer",
            transition: "all 0.15s",
          }}
        >
          KDJ K:{kdjK} D:{kdjD} J:{kdjJ}
        </button>
      </div>

      <ReactECharts
        option={option}
        style={{ height: showKdj ? 480 : 380, width: "100%" }}
        notMerge
      />
    </div>
  );
}
