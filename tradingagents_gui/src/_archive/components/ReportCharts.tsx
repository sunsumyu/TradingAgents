import { Component, type ReactNode } from "react";
import type { ChartData } from "../lib/types";
import KlineChart from "./charts/KlineChart";
import MacdChart from "./charts/MacdChart";
import RsiChart from "./charts/RsiChart";
import BollingerChart from "./charts/BollingerChart";
import SignalDashboard from "./charts/SignalDashboard";
import FundFlowChart from "./charts/FundFlowChart";

interface Props {
  chartData: ChartData;
}

// ── Error boundary so a single chart crash doesn't kill the entire report ──

interface BoundaryState {
  error: Error | null;
}

class ChartBoundary extends Component<{ title: string; children: ReactNode }, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="bg-[#1E222D] rounded-lg border border-[#363A45] p-4">
          <div className="text-[12px] text-[#FF6B6B] mb-1">图表加载失败: {this.props.title}</div>
          <div className="text-[11px] text-[#787B86]">{this.state.error.message}</div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function ReportCharts({ chartData }: Props) {
  const hasAnyChart =
    chartData.kline ||
    chartData.macd ||
    chartData.rsi ||
    chartData.bollinger ||
    chartData.dashboard ||
    chartData.fundFlow;

  if (!hasAnyChart) return null;

  // Count how many sub-indicators we have
  const subIndicatorCount = [
    chartData.macd,
    chartData.rsi,
    chartData.bollinger,
  ].filter(Boolean).length;

  // Use 3 columns when we have 3 indicators, otherwise 2
  const gridCols = subIndicatorCount === 3
    ? "grid-cols-1 md:grid-cols-3"
    : "grid-cols-1 lg:grid-cols-2";

  return (
    <div className="chart-section mb-6 space-y-3">
      {/* Dashboard — compact signal bar at top */}
      {chartData.dashboard && (
        <ChartCard title="信号仪表盘">
          <ChartBoundary title="信号仪表盘">
            <SignalDashboard data={chartData.dashboard} />
          </ChartBoundary>
        </ChartCard>
      )}

      {/* K-line chart — full width, TradingView-style */}
      {chartData.kline && (
        <ChartCard title="K线图">
          <ChartBoundary title="K线图">
            <KlineChart data={chartData.kline} />
          </ChartBoundary>
        </ChartCard>
      )}

      {/* Technical indicators — adaptive grid */}
      <div className={`grid ${gridCols} gap-3`}>
        {chartData.macd && (
          <ChartCard title="MACD">
            <ChartBoundary title="MACD">
              <MacdChart data={chartData.macd} />
            </ChartBoundary>
          </ChartCard>
        )}
        {chartData.rsi && (
          <ChartCard title="RSI">
            <ChartBoundary title="RSI">
              <RsiChart data={chartData.rsi} />
            </ChartBoundary>
          </ChartCard>
        )}
        {chartData.bollinger && (
          <ChartCard title="布林带">
            <ChartBoundary title="布林带">
              <BollingerChart data={chartData.bollinger} />
            </ChartBoundary>
          </ChartCard>
        )}
      </div>

      {/* Fund flow — full width */}
      {chartData.fundFlow && (
        <ChartCard title="资金流向">
          <ChartBoundary title="资金流向">
            <FundFlowChart data={chartData.fundFlow} />
          </ChartBoundary>
        </ChartCard>
      )}
    </div>
  );
}

function ChartCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-[#1E222D] rounded-lg border border-[#363A45] overflow-hidden">
      <div className="px-4 py-2 border-b border-[#363A45]">
        <h3 className="text-[13px] font-medium text-[#D1D4DC]">{title}</h3>
      </div>
      <div className="p-2">{children}</div>
    </div>
  );
}
