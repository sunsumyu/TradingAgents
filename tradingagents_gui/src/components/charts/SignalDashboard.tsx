import ReactECharts from "echarts-for-react";
import type { DashboardData } from "../../lib/types";
import { SIGNAL_COLORS } from "../../lib/echarts-theme";

interface Props {
  data: DashboardData;
}

export default function SignalDashboard({ data }: Props) {
  const signalColor = SIGNAL_COLORS[data.signal] || "#787B86";

  const option = {
    animation: true,
    animationDuration: 1500,
    animationEasing: "cubicOut",
    tooltip: { show: false },
    // Gauge for signal + confidence
    series: [
      // Outer gauge ring
      {
        type: "gauge",
        center: ["30%", "55%"],
        radius: "80%",
        min: 0,
        max: 100,
        startAngle: 220,
        endAngle: -40,
        progress: {
          show: true,
          width: 14,
          itemStyle: { color: signalColor },
        },
        axisLine: {
          lineStyle: { width: 14, color: [[1, "#2A2E39"]] },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        anchor: { show: false },
        title: {
          show: true,
          offsetCenter: [0, "30%"],
          fontSize: 14,
          color: "#D1D4DC",
          fontWeight: "bold",
        },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, "-5%"],
          fontSize: 28,
          fontWeight: "bold",
          color: signalColor,
          formatter: () => data.signal,
        },
        data: [{ value: data.confidence, name: `${data.confidence.toFixed(0)}% confidence` }],
      },
      // Radar chart for dimension scores
      ...(data.scores.length > 0
        ? [
            {
              type: "radar",
              center: ["72%", "55%"],
              radius: "45%",
              data: [
                {
                  value: data.scores.map((s) => s.value),
                  name: "Dimensions",
                  areaStyle: { color: `${signalColor}22` },
                  lineStyle: { color: signalColor, width: 2 },
                  itemStyle: { color: signalColor },
                },
              ],
              indicator: data.scores.map((s) => ({
                name: s.name,
                max: s.max,
              })),
              shape: "polygon",
              splitNumber: 4,
              axisName: { color: "#787B86", fontSize: 11 },
              splitLine: { lineStyle: { color: "#2A2E39" } },
              splitArea: { show: false },
              axisLine: { lineStyle: { color: "#363A45" } },
            },
          ]
        : []),
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 220, width: "100%" }}
      notMerge
    />
  );
}
