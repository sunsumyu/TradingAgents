import { ArrowLeft, Play, Loader2 } from "lucide-react";
import FundamentalCards from "./charts/FundamentalCards";
import NewsFeed from "./charts/NewsFeed";
import TradingViewLayout from "./tradingview/TradingViewLayout";
import AstockFeatureTabs from "./astock/AstockFeatureTabs";
import { useMarketDataStore } from "../stores/useMarketDataStore";
import { useAnalysisStore } from "../stores/useAnalysisStore";
import { useConfigStore } from "../stores/useConfigStore";

export default function MarketDataPanel() {
  const data = useMarketDataStore((s) => s.data);
  const error = useMarketDataStore((s) => s.error);
  const navigateTo = useAnalysisStore((s) => s.navigateTo);
  const startAnalysis = useAnalysisStore((s) => s.startAnalysis);
  const config = useConfigStore((s) => s.config);

  // ── Loading state — show immediately when data hasn't arrived yet ──
  if (!data) {
    return (
      <div className="h-full flex flex-col bg-[#131722]">
        {/* Top bar */}
        <div className="h-11 shrink-0 border-b border-[#2B2B43] flex items-center px-5">
          <button className="btn-ghost" onClick={() => navigateTo("config")}>
            <ArrowLeft size={13} />
            返回配置
          </button>
        </div>

        {/* Loading or error */}
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          {error ? (
            <>
              <span className="text-sm text-[#F23645]">✕ {error}</span>
              <button className="btn-ghost text-xs" onClick={() => navigateTo("config")}>
                返回配置
              </button>
            </>
          ) : (
            <>
              <Loader2 size={28} className="animate-spin text-[#2962FF]" />
              <span className="text-sm text-[#787B86]">正在获取市场数据…</span>
              <span className="text-[11px] text-[#4C525E]">正在从数据源获取 K 线、指标和基本面数据</span>
            </>
          )}
        </div>
      </div>
    );
  }

  const hasAnyChart = data.kline || data.macd || data.rsi || data.bollinger || data.fund_flow;

  return (
    <div className="h-full flex flex-col">
      {/* ── TradingView Chart (full screen when chart data exists) ── */}
      {hasAnyChart ? (
        <div className="flex flex-col flex-1 min-h-0">
          <TradingViewLayout
            kline={data.kline}
            macd={data.macd}
            rsi={data.rsi}
            bollinger={data.bollinger}
            ticker={data.ticker}
            name={data.fundamentals?.name ?? undefined}
          />
          <AstockFeatureTabs ticker={data.ticker} date={data.date} />
        </div>
      ) : (
        <>
          {/* ── Top Bar (no chart) ── */}
          <div className="h-11 shrink-0 border-b border-[#363A45] flex items-center px-5">
            <button className="btn-ghost" onClick={() => navigateTo("config")}>
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
                onClick={() => startAnalysis(config)}
              >
                <Play size={13} />
                开始分析
              </button>
            </div>
          </div>

          {/* ── Scrollable Content (no chart) ── */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {data.fundamentals && <FundamentalCards data={data.fundamentals} />}
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
          <AstockFeatureTabs ticker={data.ticker} date={data.date} />
        </>
      )}
    </div>
  );
}
