/**
 * MarketOverviewPage — 市场全局数据页面（对标通达信「市场」菜单）。
 *
 * 二级 Tab 架构：
 * ┌──────────────────────────────────────────────────────┐
 * │ [全景图] [新股中心] [融资融券] [投资日历] [龙虎汇总]    │
 * ├──────────────────────────────────────────────────────┤
 * │  各 Tab 独立内容区域                                    │
 * ──────────────────────────────────────────────────────┘
 *
 * 全景图: 指数分时 + 涨跌幅排行 + 板块排行 + 资讯 + 市场宽度
 * 新股中心: 发行预告 + 上市预告
 * 融资融券: 个股明细 + 市场统计 + 行业分布
 * 投资日历: 新股/停复牌/解禁聚合
 * 龙虎汇总: 席位活跃度 + 股票活跃度
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import type {
  MarketOverviewData,
  IndexTrend,
  IpoDeclarationData,
  IpoListingData,
  InvestmentCalendarData,
  AstockFeatureEnvelope,
  FundPurchaseData,
  IndustryChainData,
  IndustryDataOverview,
  MacroAnalysisData,
} from "../../lib/types";
import { api } from "../../lib/api";
import { useMarketDataStore } from "../../stores/useMarketDataStore";
import { useAnalysisStore } from "../../stores/useAnalysisStore";
import IndexChartsRow from "./IndexChartsRow";
import StockRankingPanel from "./StockRankingPanel";
import BoardRankingTable from "./BoardRankingTable";
import NewsFeed from "./NewsFeed";
import MiniChart from "./MiniChart";
import MarketStatusBar from "./MarketStatusBar";
import IpoCenterPanel from "../astock/IpoCenterPanel";
import MarginTradingPanel from "../astock/MarginTradingPanel";
import InvestmentCalendarPanel from "../astock/InvestmentCalendarPanel";
import MarkdownRenderer from "../shared/Markdown";
import DataSourceNotice from "./DataSourceNotice";
import BlockTradePanel from "../astock/BlockTradePanel";
import DividendBonusPanel from "../astock/DividendBonusPanel";
import EarningsForecastPanel from "../astock/EarningsForecastPanel";
import AnalystRatingPanel from "../astock/AnalystRatingPanel";
import InstitutionalHoldPanel from "../astock/InstitutionalHoldPanel";
import FundFlowPanel from "../astock/FundFlowPanel";
import PledgePanel from "../astock/PledgePanel";
import BuybackPanel from "../astock/BuybackPanel";
import ConvertBondPanel from "../astock/ConvertBondPanel";
import FundDataPanel from "./FundDataPanel";
import IndustryChainPanel from "./IndustryChainPanel";
import IndustryDataPanel from "./IndustryDataPanel";
import MacroAnalysisPanel from "./MacroAnalysisPanel";
import { SeatActivityPanel, StockActivityPanel } from "./DragonActivityPanel";
import MarketTablePanel from "./MarketTablePanel";

const REFRESH_INTERVAL = 30_000; // 30 seconds

type MarketTab = "overview" | "ipo" | "margin" | "calendar" | "dragon" | "block_trade" | "dividend" | "earnings" | "analyst" | "institutional" | "fundflow" | "pledge" | "buyback" | "convert" | "survey" | "reference" | "neeq" | "futures" | "hk" | "us" | "stats" | "fund" | "chain" | "industry" | "macro";

const MARKET_TABS: { key: MarketTab; label: string }[] = [
  { key: "overview", label: "全景" },
  { key: "ipo", label: "新股" },
  { key: "margin", label: "融资" },
  { key: "calendar", label: "日历" },
  { key: "dragon", label: "龙虎" },
  { key: "block_trade", label: "大宗" },
  { key: "dividend", label: "增发" },
  { key: "earnings", label: "财报" },
  { key: "analyst", label: "价值" },
  { key: "institutional", label: "机构" },
  { key: "fundflow", label: "资金" },
  { key: "pledge", label: "质押" },
  { key: "buyback", label: "回购" },
  { key: "convert", label: "转债" },
  { key: "stats", label: "统计" },
  // TongDaXin reference data
  { key: "survey", label: "调研" },
  { key: "reference", label: "备查" },
  { key: "neeq", label: "三板" },
  { key: "futures", label: "股指" },
  { key: "hk", label: "港股" },
  { key: "us", label: "美股" },
  // Phase 10: TongDaXin 数据菜单
  { key: "fund", label: "基金" },
  { key: "chain", label: "产业" },
  { key: "industry", label: "行业" },
  { key: "macro", label: "宏观" },
];

export default function MarketOverviewPage() {
  const [activeTab, setActiveTab] = useState<MarketTab>("overview");
  const [data, setData] = useState<MarketOverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<{ code: string; name: string } | null>(null);
  const [stockTrends, setStockTrends] = useState<IndexTrend[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const fetchMarketData = useMarketDataStore((s) => s.fetchMarketData);
  const navigateTo = useAnalysisStore((s) => s.navigateTo);

  // Cache for global features (lazy loaded per tab)
  const [globalCache, setGlobalCache] = useState<Map<string, AstockFeatureEnvelope>>(new Map());

  const fetchData = useCallback(async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const resp = await api.getMarketOverview(ctrl.signal);
      setData(resp);
      setError(null);
    } catch (err: any) {
      if (err?.name === "AbortError") return;
      setError(err?.message ?? String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch global feature on demand
  const fetchGlobalFeature = useCallback(async (feature: string) => {
    if (globalCache.has(feature)) return;
    try {
      const resp = await api.getAstockFeature(feature, "000000", new Date().toISOString().slice(0, 10));
      setGlobalCache((prev) => new Map(prev).set(feature, resp));
    } catch (err) {
      // Silently fail — panel will show raw_md fallback
    }
  }, [globalCache]);

  // Fetch overview on mount
  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, REFRESH_INTERVAL);
    return () => {
      clearInterval(timer);
      abortRef.current?.abort();
    };
  }, [fetchData]);

  // Lazy-load global feature when tab is activated
  useEffect(() => {
    if (activeTab === "ipo") {
      fetchGlobalFeature("ipo_declaration");
      fetchGlobalFeature("ipo_listing");
    } else if (activeTab === "margin") {
      fetchGlobalFeature("margin_detail");
      fetchGlobalFeature("margin_market_stat");
    } else if (activeTab === "calendar") {
      fetchGlobalFeature("investment_calendar");
    } else if (activeTab === "dragon") {
      fetchGlobalFeature("seat_activity");
      fetchGlobalFeature("stock_activity");
    } else if (activeTab === "block_trade") {
      fetchGlobalFeature("block_trade_detail");
      fetchGlobalFeature("block_trade_industry");
      fetchGlobalFeature("block_trade_market_stat");
    } else if (activeTab === "dividend") {
      fetchGlobalFeature("dividend_bonus");
    } else if (activeTab === "earnings") {
      fetchGlobalFeature("earnings_forecast");
      fetchGlobalFeature("earnings_express");
    } else if (activeTab === "analyst") {
      fetchGlobalFeature("analyst_rating");
    } else if (activeTab === "institutional") {
      fetchGlobalFeature("institutional_hold");
    } else if (activeTab === "fundflow") {
      fetchGlobalFeature("industry_fund_flow");
      fetchGlobalFeature("concept_fund_flow");
    } else if (activeTab === "pledge") {
      fetchGlobalFeature("pledge_market");
      fetchGlobalFeature("pledge_industry");
      fetchGlobalFeature("pledge_stock");
    } else if (activeTab === "buyback") {
      fetchGlobalFeature("buyback");
    } else if (activeTab === "convert") {
      fetchGlobalFeature("convert_bond_list");
    } else if (activeTab === "survey") {
      fetchGlobalFeature("survey_interaction");
    } else if (activeTab === "reference") {
      fetchGlobalFeature("company_name_changes");
      fetchGlobalFeature("st_changes");
    } else if (activeTab === "neeq") {
      fetchGlobalFeature("neeq_abnormal_trade");
    } else if (activeTab === "futures") {
      fetchGlobalFeature("futures_position");
    } else if (activeTab === "hk") {
      fetchGlobalFeature("hk_ipo");
    } else if (activeTab === "us") {
      fetchGlobalFeature("us_ipo");
    } else if (activeTab === "stats") {
      fetchGlobalFeature("market_statistics");
    } else if (activeTab === "fund") {
      fetchGlobalFeature("fund_purchase");
      fetchGlobalFeature("fund_announcement");
      fetchGlobalFeature("fund_scale");
      fetchGlobalFeature("fund_open_info");
    } else if (activeTab === "chain") {
      fetchGlobalFeature("industry_chain_categories");
      fetchGlobalFeature("industry_chain_chains");
    } else if (activeTab === "industry") {
      fetchGlobalFeature("industry_list");
      fetchGlobalFeature("industry_commodity");
    } else if (activeTab === "macro") {
      fetchGlobalFeature("macro_gdp");
      fetchGlobalFeature("macro_cpi");
      fetchGlobalFeature("macro_pmi");
    }
  }, [activeTab, fetchGlobalFeature]);

  // Load stock trends when a stock is selected
  useEffect(() => {
    if (!selectedStock) return;
    let cancelled = false;
    api.getStockTrends(selectedStock.code).then((trends) => {
      if (!cancelled) setStockTrends(trends);
    }).catch(() => {
      if (!cancelled) setStockTrends([]);
    });
    return () => { cancelled = true; };
  }, [selectedStock]);

  const handleStockClick = useCallback((code: string) => {
    let name = code;
    const allRankings = [
      ...(data?.sh_gainers ?? []),
      ...(data?.sh_losers ?? []),
      ...(data?.sz_gainers ?? []),
      ...(data?.sz_losers ?? []),
    ];
    const found = allRankings.find((s) => s.code === code);
    if (found) name = found.name;
    setSelectedStock({ code, name });
    // Navigate to stock detail page
    const today = new Date().toISOString().split("T")[0];
    fetchMarketData(code, today).then(() => {
      navigateTo("market_data");
    });
  }, [data, fetchMarketData, navigateTo]);

  const declEnv = globalCache.get("ipo_declaration");
  const listEnv = globalCache.get("ipo_listing");
  const marginDetailEnv = globalCache.get("margin_detail");
  const marginStatEnv = globalCache.get("margin_market_stat");
  const calendarEnv = globalCache.get("investment_calendar");
  const seatEnv = globalCache.get("seat_activity");
  const stockActEnv = globalCache.get("stock_activity");
  const dividendEnv = globalCache.get("dividend_bonus");
  const analystEnv = globalCache.get("analyst_rating");
  const instHoldEnv = globalCache.get("institutional_hold");
  const fundPurchaseEnv = globalCache.get("fund_purchase");
  const chainCatsEnv = globalCache.get("industry_chain_categories");
  const chainChainsEnv = globalCache.get("industry_chain_chains");
  const industryListEnv = globalCache.get("industry_list");
  const industryCommodityEnv = globalCache.get("industry_commodity");
  const macroGdpEnv = globalCache.get("macro_gdp");
  const macroCpiEnv = globalCache.get("macro_cpi");
  const macroPmiEnv = globalCache.get("macro_pmi");

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-full gap-2 text-[#787B86] text-sm">
        <Loader2 size={16} className="animate-spin" />
        加载市场数据…
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <span className="text-sm text-[#F23645]">✕ {error}</span>
        <button onClick={fetchData} className="text-xs text-[#2962FF] hover:underline flex items-center gap-1">
          <RefreshCw size={12} /> 重试
        </button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="h-full flex flex-col bg-[#0D1117]">
      {/* Secondary Tab Bar */}
      <div className="flex items-center gap-0 border-b border-[#1E222D] px-2 bg-[#131722] overflow-x-auto whitespace-nowrap scrollbar-thin scrollbar-thumb-[#2A2E39]">
        {MARKET_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-[12px] transition-colors ${
              activeTab === tab.key
                ? "text-[#2962FF] border-b-2 border-[#2962FF] font-medium"
                : "text-[#787B86] hover:text-[#D1D4DC]"
            }`}
          >
            {tab.label}
          </button>
        ))}
        <span className="ml-auto text-[10px] text-[#4C525E] pr-2">{data.timestamp}</span>
      </div>

      {/* Tab Content */}
      {activeTab === "overview" && (
        <>
          {/* Index Charts Row */}
          <div className="h-[200px] flex-shrink-0 border-b border-[#1E222D]">
            <IndexChartsRow indices={data.indices} />
          </div>

          {/* Rankings + Boards */}
          <div className="flex-1 min-h-0 flex">
            <div className="w-[320px] flex-shrink-0 flex flex-col border-r border-[#1E222D]">
              <div className="flex-1 min-h-0 border-b border-[#1E222D]">
                <StockRankingPanel
                  title="上证A股"
                  gainers={data.sh_gainers}
                  losers={data.sh_losers}
                  onStockClick={handleStockClick}
                />
              </div>
              <div className="flex-1 min-h-0">
                <StockRankingPanel
                  title="深证A股"
                  gainers={data.sz_gainers}
                  losers={data.sz_losers}
                  onStockClick={handleStockClick}
                />
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <BoardRankingTable
                boards={data.boards}
                onBoardClick={(code) => handleStockClick(code)}
              />
            </div>
          </div>

          {/* News + MiniChart */}
          <div className="h-[220px] flex-shrink-0 flex border-t border-[#1E222D]">
            <div className="w-[400px] flex-shrink-0 border-r border-[#1E222D]">
              <NewsFeed news={data.news} />
            </div>
            <div className="flex-1 min-w-0">
              <MiniChart
                ticker={selectedStock?.code ?? null}
                name={selectedStock?.name}
                trends={stockTrends}
              />
            </div>
          </div>

          {/* Status Bar */}
          <MarketStatusBar breadth={data.breadth} timestamp={data.timestamp} />
        </>
      )}

      {activeTab === "ipo" && (
        <IpoCenterPanel
          declarationData={declEnv?.data as unknown as IpoDeclarationData}
          listingData={listEnv?.data as unknown as IpoListingData}
          declarationMd={declEnv?.raw_md ?? ""}
          listingMd={listEnv?.raw_md ?? ""}
        />
      )}

      {activeTab === "margin" && (
        <div className="h-full flex flex-col">
          <div className="flex-1 min-h-0">
            <MarginTradingPanel
              data={marginDetailEnv?.data}
              rawMd={marginDetailEnv?.raw_md ?? ""}
              feature="margin_detail"
            />
          </div>
          <div className="h-[200px] border-t border-[#1E222D]">
            <MarginTradingPanel
              data={marginStatEnv?.data}
              rawMd={marginStatEnv?.raw_md ?? ""}
              feature="margin_market_stat"
            />
          </div>
        </div>
      )}

      {activeTab === "calendar" && (
        calendarEnv ? (
          <InvestmentCalendarPanel
            data={calendarEnv.data as unknown as InvestmentCalendarData}
            rawMd={calendarEnv.raw_md ?? ""}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-[#787B86] text-xs">加载中…</div>
        )
      )}

      {activeTab === "dragon" && (
        <div className="h-full flex flex-col">
          <div className="flex-1 min-h-0 border-b border-[#1E222D]">
            <SeatActivityPanel
              data={seatEnv?.data as Record<string, unknown> | undefined}
              rawMd={seatEnv?.raw_md ?? ""}
            />
          </div>
          <div className="flex-1 min-h-0">
            <StockActivityPanel
              data={stockActEnv?.data as Record<string, unknown> | undefined}
              rawMd={stockActEnv?.raw_md ?? ""}
            />
          </div>
        </div>
      )}

      {activeTab === "block_trade" && (
        <div className="h-full flex flex-col">
          <div className="flex-1 min-h-0 border-b border-[#1E222D]">
            <BlockTradePanel
              data={globalCache.get("block_trade_detail")?.data}
              rawMd={globalCache.get("block_trade_detail")?.raw_md ?? ""}
            />
          </div>
          <div className="flex-1 min-h-0 border-b border-[#1E222D]">
            <BlockTradePanel
              data={globalCache.get("block_trade_industry")?.data}
              rawMd={globalCache.get("block_trade_industry")?.raw_md ?? ""}
            />
          </div>
          <div className="flex-1 min-h-0">
            <BlockTradePanel
              data={globalCache.get("block_trade_market_stat")?.data}
              rawMd={globalCache.get("block_trade_market_stat")?.raw_md ?? ""}
            />
          </div>
        </div>
      )}

      {activeTab === "dividend" && (
        <div className="h-full min-h-0">
          <DividendBonusPanel data={dividendEnv?.data} rawMd={dividendEnv?.raw_md ?? ""} />
        </div>
      )}

      {activeTab === "earnings" && (
        <div className="h-full flex flex-col">
          <div className="flex-1 min-h-0 border-b border-[#1E222D]">
            <EarningsForecastPanel
              data={globalCache.get("earnings_forecast")?.data}
              rawMd={globalCache.get("earnings_forecast")?.raw_md ?? ""}
            />
          </div>
          <div className="flex-1 min-h-0">
            <EarningsForecastPanel
              data={globalCache.get("earnings_express")?.data}
              rawMd={globalCache.get("earnings_express")?.raw_md ?? ""}
            />
          </div>
        </div>
      )}

      {activeTab === "analyst" && (
        <div className="h-full min-h-0">
          <AnalystRatingPanel data={analystEnv?.data} rawMd={analystEnv?.raw_md ?? ""} />
        </div>
      )}

      {activeTab === "institutional" && (
        <div className="h-full min-h-0">
          <InstitutionalHoldPanel data={instHoldEnv?.data} rawMd={instHoldEnv?.raw_md ?? ""} />
        </div>
      )}

      {activeTab === "fundflow" && (
        <div className="h-full min-h-0">
          <FundFlowPanel
            industry={globalCache.get("industry_fund_flow")?.data}
            concept={globalCache.get("concept_fund_flow")?.data}
            industryRawMd={globalCache.get("industry_fund_flow")?.raw_md ?? ""}
            conceptRawMd={globalCache.get("concept_fund_flow")?.raw_md ?? ""}
          />
        </div>
      )}

      {activeTab === "pledge" && (
        <div className="h-full min-h-0">
          <PledgePanel
            market={globalCache.get("pledge_market")?.data}
            industry={globalCache.get("pledge_industry")?.data}
            stock={globalCache.get("pledge_stock")?.data}
            marketRawMd={globalCache.get("pledge_market")?.raw_md ?? ""}
            industryRawMd={globalCache.get("pledge_industry")?.raw_md ?? ""}
            stockRawMd={globalCache.get("pledge_stock")?.raw_md ?? ""}
          />
        </div>
      )}

      {activeTab === "buyback" && (
        <div className="h-full min-h-0">
          <BuybackPanel
            data={globalCache.get("buyback")?.data}
            rawMd={globalCache.get("buyback")?.raw_md ?? ""}
          />
        </div>
      )}

      {activeTab === "convert" && (
        <div className="h-full min-h-0">
          <ConvertBondPanel
            data={globalCache.get("convert_bond_list")?.data}
            rawMd={globalCache.get("convert_bond_list")?.raw_md ?? ""}
          />
        </div>
      )}

      {activeTab === "stats" && (
        <MarketTablePanel
          rawMd={globalCache.get("market_statistics")?.raw_md ?? ""}
          tables={[
            {
              title: "市场规模统计",
              accent: "#2962FF",
              items: (globalCache.get("market_statistics")?.data as any)?.scale?.items ?? [],
              columns: [
                { key: "exchange", label: "交易所", unit: "text", format: "text" },
                { key: "listed_stocks", label: "上市股票数", unit: "count", format: "int" },
                { key: "listed_companies", label: "上市公司数", unit: "count", format: "int" },
                { key: "market_cap_yi", label: "市价总值(亿)", unit: "亿元", format: "float2" },
                { key: "float_cap_yi", label: "流通市值(亿)", unit: "亿元", format: "float2" },
                { key: "float_shares_yi", label: "流通股本(亿股)", unit: "亿股", format: "float2" },
                { key: "pe_avg", label: "平均市盈率", unit: "ratio", format: "float2" },
                { key: "pe_star", label: "科创板市盈率", unit: "ratio", format: "float2" },
              ],
            },
            {
              title: "成交概况（品种分类）",
              accent: "#26A69A",
              items: (globalCache.get("market_statistics")?.data as any)?.turnover?.items ?? [],
              columns: [
                { key: "market", label: "市场", unit: "text", format: "text" },
                { key: "variety", label: "品种", unit: "text", format: "text" },
                { key: "count", label: "数量", unit: "count", format: "int" },
                { key: "amount_yi", label: "成交金额(亿)", unit: "亿元", format: "float2" },
              ],
            },
            {
              title: "投资者情况（中国结算月度）",
              accent: "#FF9800",
              items: (globalCache.get("market_statistics")?.data as any)?.investors?.items ?? [],
              columns: [
                { key: "month", label: "月份", unit: "text", format: "text" },
                { key: "new_investors_wan", label: "新增投资者(万)", unit: "count", format: "float2" },
                { key: "total_investors_wan", label: "期末总量(万)", unit: "count", format: "float2" },
                { key: "a_account_wan", label: "A股账户(万)", unit: "count", format: "float2" },
                { key: "total_cap_yi", label: "沪深总市值(亿)", unit: "亿元", format: "float2" },
                { key: "avg_cap_wan", label: "户均市值(万)", unit: "万元", format: "float2" },
              ],
            },
          ]}
        />
      )}

      {activeTab === "survey" && (
        <MarketTablePanel
          rawMd={globalCache.get("survey_interaction")?.raw_md ?? ""}
          tables={[
            {
              title: "调研互动（机构调研统计）",
              accent: "#E040FB",
              items: (globalCache.get("survey_interaction")?.data as any)?.items ?? [],
              columns: [
                { key: "code", label: "代码", unit: "text", format: "text" },
                { key: "name", label: "简称", unit: "text", format: "text" },
                { key: "industry", label: "所属行业", unit: "text", format: "text" },
                { key: "last_survey_date", label: "最新调研日", unit: "date", format: "date" },
                { key: "survey_1m", label: "近一月调研", unit: "count", format: "int" },
                { key: "survey_3m", label: "近三月调研", unit: "count", format: "int" },
                { key: "survey_6m", label: "近半年调研", unit: "count", format: "int" },
                { key: "inst_1m", label: "近一月机构", unit: "count", format: "int" },
                { key: "inst_3m", label: "近三月机构", unit: "count", format: "int" },
                { key: "inst_6m", label: "近半年机构", unit: "count", format: "int" },
                { key: "price", label: "最新价", unit: "元", format: "float2" },
                { key: "change_pct", label: "涨跌幅", unit: "percent", format: "float2" },
              ],
            },
          ]}
        />
      )}

      {activeTab === "reference" && (
        <div className="h-full flex flex-col">
          <div className="flex-1 min-h-0 border-b border-[#1E222D] overflow-y-auto">
            <DataSourceNotice kind="partial">
              数据源：深交所-名称变更（简称变更 7482 行 / 全称变更 1762 行，已实测）。仅覆盖深市证券，沪市更名不在该源中。
            </DataSourceNotice>
            {globalCache.get("company_name_changes")?.raw_md ? (
              <MarkdownRenderer markdown={globalCache.get("company_name_changes")!.raw_md} className="p-3" />
            ) : (
              <div className="flex items-center justify-center h-full text-[#787B86] text-xs">加载中…</div>
            )}
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto">
            <DataSourceNotice kind="partial">
              ST 变更由深交所简称变更记录派生（变更后含 ST → 实施，变更前含 → 撤销）。仅覆盖深市证券；沪市 ST 变更不在该源中。
            </DataSourceNotice>
            {globalCache.get("st_changes")?.raw_md ? (
              <MarkdownRenderer markdown={globalCache.get("st_changes")!.raw_md} className="p-3" />
            ) : (
              <div className="flex items-center justify-center h-full text-[#787B86] text-xs">加载中…</div>
            )}
          </div>
        </div>
      )}

      {activeTab === "neeq" && (
        <div className="h-full overflow-y-auto">
          <DataSourceNotice kind="unavailable">
            三板异常交易暂无公开 API 数据源（东财 datacenter 已探测无对应 reportName）。
          </DataSourceNotice>
          {globalCache.get("neeq_abnormal_trade")?.raw_md ? (
            <MarkdownRenderer markdown={globalCache.get("neeq_abnormal_trade")!.raw_md} className="p-3" />
          ) : (
            <div className="flex items-center justify-center h-full text-[#787B86] text-xs">加载中…</div>
          )}
        </div>
      )}

      {activeTab === "futures" && (
        <div className="h-full overflow-y-auto">
          {globalCache.get("futures_position")?.raw_md ? (
            <MarkdownRenderer markdown={globalCache.get("futures_position")!.raw_md} className="p-3" />
          ) : (
            <div className="flex items-center justify-center h-full text-[#787B86] text-xs">加载中…</div>
          )}
        </div>
      )}

      {activeTab === "hk" && (
        <div className="h-full overflow-y-auto">
          <DataSourceNotice kind="partial">
            数据源：阿斯达克 aastocks 新股频道（2026-09-28 换源，已实测验证为港股代码）。覆盖招股中 + 近期已上市概览，非完整招股书数据；东财港股新股页已下线（404）。
          </DataSourceNotice>
          {globalCache.get("hk_ipo")?.raw_md ? (
            <MarkdownRenderer markdown={globalCache.get("hk_ipo")!.raw_md} className="p-3" />
          ) : (
            <div className="flex items-center justify-center h-full text-[#787B86] text-xs">加载中…</div>
          )}
        </div>
      )}

      {activeTab === "us" && (
        <div className="h-full overflow-y-auto">
          <DataSourceNotice kind="unavailable">
            美股 IPO 暂无公开 API 数据源（东财 datacenter 已探测无对应 reportName）。
          </DataSourceNotice>
          {globalCache.get("us_ipo")?.raw_md ? (
            <MarkdownRenderer markdown={globalCache.get("us_ipo")!.raw_md} className="p-3" />
          ) : (
            <div className="flex items-center justify-center h-full text-[#787B86] text-xs">加载中…</div>
          )}
        </div>
      )}

      {/* 基金数据 */}
      {activeTab === "fund" && (
        <FundDataPanel
          data={fundPurchaseEnv?.data as unknown as FundPurchaseData}
          rawMd={fundPurchaseEnv?.raw_md ?? ""}
        />
      )}

      {/* 产业链 */}
      {activeTab === "chain" && (
        <IndustryChainPanel
          data={
            chainCatsEnv || chainChainsEnv
              ? ({
                  categories: chainCatsEnv?.data,
                  chains: chainChainsEnv?.data,
                } as unknown as IndustryChainData)
              : undefined
          }
          rawMd={chainCatsEnv?.raw_md ?? chainChainsEnv?.raw_md ?? ""}
        />
      )}

      {/* 行业数据 */}
      {activeTab === "industry" && (
        <IndustryDataPanel
          data={
            industryListEnv || industryCommodityEnv
              ? ({
                  list: industryListEnv?.data,
                  commodity: industryCommodityEnv?.data,
                } as unknown as IndustryDataOverview)
              : undefined
          }
          rawMd={industryListEnv?.raw_md ?? industryCommodityEnv?.raw_md ?? ""}
        />
      )}

      {/* 宏观分析 */}
      {activeTab === "macro" && (
        <MacroAnalysisPanel
          data={macroGdpEnv?.data as unknown as MacroAnalysisData}
          rawMd={macroGdpEnv?.raw_md ?? ""}
          cpiData={macroCpiEnv?.data}
          pmiData={macroPmiEnv?.data}
        />
      )}
    </div>
  );
}
