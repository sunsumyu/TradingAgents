import { ArrowLeft, Play, Loader2 } from "lucide-react";
import type { MarketDataResponse } from "../lib/types";
import FundamentalCards from "./charts/FundamentalCards";
import NewsFeed from "./charts/NewsFeed";
import ReportCharts from "./ReportCharts";

interface Props {
  data: MarketDataResponse;
  onBack: () => void;
  onAnalyze: () => void;
  isAnalyzing?: boolean;
}

export default function MarketDataPanel({ data, onBack, onAnalyze, isAnalyzing }: Props) {
  // Build a ChartData-compatible object from MarketDataResponse
  const chartData = {
    kline: data.kline,
    macd: data.macd,
    rsi: data.rsi,
    bollinger: data.bollinger,
    fundFlow: data.fund_flow,
    dashboard: null, // No signal yet — that comes from agent analysis
  };

  const hasAnyChart = data.kline || data.macd || data.rsi || data.bollinger || data.fund_flow;

  return (
    <div className="h-full flex flex-col">
      {/* ── Top Bar ── */}
      <div className="h-11 shrink-0 border-b border-[#363A45] flex items-center px-5">
        <button className="btn-ghost" onClick={onBack}>
          <ArrowLeft size={13} />
          返回配置
        </button>
        <h1 className="text-[18px] font-semibold text-[#D1D4DC] ml-3">
          {data.ticker}
          {data.fundamentals?.name && (
            <span className="text-[13px] text-[#787B86] font-normal ml-2">
              {data.fundamentals.name}
            </span>
          )}
        </h1>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[11px] text-[#787B86]">{data.date}</span>
          <button
            className="btn-primary"
            onClick={onAnalyze}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? (
              <>
                <Loader2 size={13} className="animate-spin" />
                分析中...
              </>
            ) : (
              <>
                <Play size={13} />
                开始分析
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Scrollable Content ── */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {/* Fundamentals cards */}
        {data.fundamentals && (
          <FundamentalCards data={data.fundamentals} />
        )}

        {/* Charts */}
        {hasAnyChart && (
          <ReportCharts chartData={chartData} />
        )}

        {/* News */}
        {data.news && data.news.length > 0 && (
          <div className="bg-[#1E222D] rounded-lg border border-[#363A45] overflow-hidden mt-3">
            <div className="px-4 py-2 border-b border-[#363A45]">
              <h3 className="text-[13px] font-medium text-[#D1D4DC]">最新新闻</h3>
            </div>
            <div className="p-2">
              <NewsFeed items={data.news} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
