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

export default function ReportCharts({ chartData }: Props) {
  const hasAnyChart =
    chartData.kline ||
    chartData.macd ||
    chartData.rsi ||
    chartData.bollinger ||
    chartData.dashboard ||
    chartData.fundFlow;

  if (!hasAnyChart) return null;

  return (
    <div className="chart-section mb-6 space-y-4">
      {/* Dashboard — always first if present */}
      {chartData.dashboard && (
        <ChartCard title="信号仪表盘">
          <SignalDashboard data={chartData.dashboard} />
        </ChartCard>
      )}

      {/* K-line chart — full width */}
      {chartData.kline && (
        <ChartCard title="K线图">
          <KlineChart data={chartData.kline} />
        </ChartCard>
      )}

      {/* Technical indicators — 2-column grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {chartData.macd && (
          <ChartCard title="MACD">
            <MacdChart data={chartData.macd} />
          </ChartCard>
        )}
        {chartData.rsi && (
          <ChartCard title="RSI">
            <RsiChart data={chartData.rsi} />
          </ChartCard>
        )}
      </div>

      {/* Bollinger — full width */}
      {chartData.bollinger && (
        <ChartCard title="布林带">
          <BollingerChart data={chartData.bollinger} />
        </ChartCard>
      )}

      {/* Fund flow — full width */}
      {chartData.fundFlow && (
        <ChartCard title="资金流向">
          <FundFlowChart data={chartData.fundFlow} />
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
