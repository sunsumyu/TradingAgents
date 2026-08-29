import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { DashboardData } from "../../lib/types";
import { SIGNAL_COLORS } from "../../lib/echarts-theme";

interface Props {
  data: DashboardData;
}

/**
 * Dashboard gauge + radar chart — TradingView-style layout.
 *
 * The radar series uses ECharts' DataDiffer which has a known bug: when
 * the chart re-renders with `setOption` (even in merge mode), the diff
 * can call `oldData.getItemGraphicEl()` on a stale index, returning
 * undefined and crashing on `.childAt()`.
 *
 * Fix: use a `key` tied to the scores data so React fully destroys and
 * recreates the ECharts instance whenever the data changes. This avoids
 * the diff entirely — each mount starts from a clean state.
 */
export default function SignalDashboard({ data }: Props) {
  const signalColor = SIGNAL_COLORS[data.signal] || "#787B86";

  // Key forces a full remount when scores change, bypassing radar DataDiffer.
  const chartKey = useMemo(
    () => `${data.signal}-${data.confidence}-${data.scores.length}-${data.scores.map((s) => s.value).join(",")}`,
    [data.signal, data.confidence, data.scores],
  );

  const option = useMemo(() => ({
    animation: true,
    animationDuration: 1500,
    animationEasing: "cubicOut",
    tooltip: { show: false },
    // Side-by-side layout: gauge on left, radar on right, with more horizontal spread
    grid: [
      { left: "5%", right: "50%", top: 20, bottom: 30 },  // gauge area
      { left: "50%", right: "5%", top: 20, bottom: 30 },  // radar area
    ],
    series: [
      {
        type: "gauge",
        center: ["25%", "52%"],
        radius: "85%",
        min: 0,
        max: 100,
        startAngle: 220,
        endAngle: -40,
        progress: {
          show: true,
          width: 16,
          itemStyle: { color: signalColor },
        },
        axisLine: {
          lineStyle: { width: 16, color: [[1, "#2A2E39"]] },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        anchor: { show: false },
        title: {
          show: true,
          offsetCenter: [0, "38%"],
          fontSize: 16,
          color: signalColor,
          fontWeight: "bold",
        },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, "-5%"],
          fontSize: 36,
          fontWeight: "bold",
          color: "#D1D4DC",
          formatter: (value: number) => `${value.toFixed(0)}%`,
        },
        data: [{ value: data.confidence, name: data.signal }],
      },
      {
        type: "radar",
        center: ["75%", "52%"],
        radius: "50%",
        data:
          data.scores.length > 0
            ? [
                {
                  value: data.scores.map((s) => s.value),
                  name: "Dimensions",
                  areaStyle: { color: `${signalColor}22` },
                  lineStyle: { color: signalColor, width: 2 },
                  itemStyle: { color: signalColor },
                },
              ]
            : [],
        indicator:
          data.scores.length > 0
            ? data.scores.map((s) => ({ name: s.name, max: s.max }))
            : [{ name: "", max: 1 }],
        shape: "polygon",
        splitNumber: 4,
        axisName: { color: "#787B86", fontSize: 11 },
        splitLine: { lineStyle: { color: "#2A2E39" } },
        splitArea: { show: false },
        axisLine: { lineStyle: { color: "#363A45" } },
        silent: data.scores.length === 0,
      },
    ],
  }), [data.confidence, data.signal, data.scores]);

  return (
    <div style={{ position: "relative" }}>
      <ReactECharts
        key={chartKey}
        option={option}
        style={{ height: 200, width: "100%" }}
      />
      <div
        style={{
          position: "absolute",
          left: "25%",
          top: "78%",
          transform: "translateX(-50%)",
          fontSize: 13,
          color: "#787B86",
          textAlign: "center",
          pointerEvents: "none",
        }}
      >
        信心指数
      </div>
    </div>
  );
}
