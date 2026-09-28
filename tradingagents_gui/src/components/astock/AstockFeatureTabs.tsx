/**
 * AstockFeatureTabs — Tab strip + lazy-loading wrapper for A-stock features.
 *
 * Design (per spec docs/specs/2026-08-26-phase5-astock-data-center.md §4.4):
 * - Lazy: first click triggers the fetch; subsequent switches show cached data.
 * - Race-safe: AbortController cancels in-flight request when the user clicks
 *   another tab before the response arrives.
 * - Only renders for A-share codes (6-digit); hidden for global tickers.
 * - Each feature panel receives { data, raw_md, loading, error }.
 * - Tabs are registered in ASTOCK_FEATURE_TABS (lib/types.ts); the key set must
 *   stay in sync with the backend FEATURE_TABLE (enforced by
 *   tests/test_feature_key_parity.py).
 * - Panels that have a dedicated component render structured data with the
 *   raw_md fallback; anything else falls back to raw_md rendering.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "../../lib/api";
import type {
  AstockFeatureEnvelope,
  AstockFeatureKey,
  ChipDistributionData,
  ConceptBlocksData,
  DragonTigerData,
  FinancialStatementData,
  HotStocksData,
  IndustryComparisonData,
  InsiderTransactionsData,
  LockupExpiryData,
  NorthboundData,
  ProfitForecastData,
} from "../../lib/types";
import { ASTOCK_FEATURE_TABS } from "../../lib/types";
import ChipPanel from "./ChipPanel";
import DragonTigerPanel from "./DragonTigerPanel";
import NorthboundPanel from "./NorthboundPanel";
import ConceptPanel from "./ConceptPanel";
import ProfitForecastPanel from "./ProfitForecastPanel";
import LockupPanel from "./LockupPanel";
import HotStockPanel from "./HotStockPanel";
import FinancialStatementPanel from "./FinancialStatementPanel";
import MarkdownRenderer from "../shared/Markdown";
import IndustryComparisonPanel from "./IndustryComparisonPanel";
import InsiderTransactionsPanel from "./InsiderTransactionsPanel";
import BlockTradePanel from "./BlockTradePanel";
import DividendBonusPanel from "./DividendBonusPanel";
import EarningsForecastPanel from "./EarningsForecastPanel";
import AnalystRatingPanel from "./AnalystRatingPanel";
import InstitutionalHoldPanel from "./InstitutionalHoldPanel";
import HolderPanel from "./HolderPanel";
import StockNoticesPanel from "./StockNoticesPanel";
import ResearchReportsPanel from "./ResearchReportsPanel";

// ── helpers ──────────────────────────────────────────────────────────────────

function isAstockCode(ticker: string): boolean {
  let t = ticker.trim().toUpperCase();
  for (const suffix of [".SH", ".SZ", ".BJ", ".SS"]) {
    if (t.endsWith(suffix)) { t = t.slice(0, -suffix.length); break; }
  }
  for (const prefix of ["SH", "SZ", "BJ"]) {
    if (t.startsWith(prefix)) { t = t.slice(prefix.length); break; }
  }
  return /^\d{6}$/.test(t);
}

// ── component ────────────────────────────────────────────────────────────────

interface Props {
  ticker: string;
  date: string;
}

type FeatureCache = Map<AstockFeatureKey, AstockFeatureEnvelope>;

export default function AstockFeatureTabs({ ticker, date }: Props) {
  const [activeTab, setActiveTab] = useState<AstockFeatureKey | null>(null);
  const [cache, setCache] = useState<FeatureCache>(new Map());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Only show tabs for A-share codes
  if (!isAstockCode(ticker)) return null;

  // For A-share codes: show all tabs (some features are market-wide like northbound_flow)

  const fetchFeature = useCallback(
    async (feature: AstockFeatureKey) => {
      // Cancel any in-flight request
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      setLoading(true);
      setError(null);

      try {
        const resp = await api.getAstockFeature(feature, ticker, date, ctrl.signal);
        setCache((prev) => new Map(prev).set(feature, resp));
      } catch (err: any) {
        if (err?.name === "AbortError") return; // cancelled, ignore
        setError(err?.message ?? String(err));
      } finally {
        setLoading(false);
      }
    },
    [ticker, date],
  );

  // Lazy fetch on first tab click
  const handleTabClick = useCallback(
    (key: AstockFeatureKey) => {
      setActiveTab(key);
      if (!cache.has(key)) {
        fetchFeature(key);
      }
    },
    [cache, fetchFeature],
  );

  // Cleanup abort on unmount
  useEffect(() => () => abortRef.current?.abort(), []);

  const activeData = activeTab ? cache.get(activeTab) : null;

  return (
    <div className="border-t border-line bg-bg-secondary">
      {/* Tab strip */}
      <div className="flex items-center gap-0 overflow-x-auto border-b border-line px-2">
        {ASTOCK_FEATURE_TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => handleTabClick(tab.key)}
              className={`px-3 py-2 text-xs whitespace-nowrap transition-colors ${
                isActive
                  ? "text-accent border-b-2 border-accent"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Feature content */}
      <div style={{ height: 320 }} className="relative">
        {!activeTab ? (
          <div className="flex items-center justify-center h-full text-text-secondary text-xs">
            点击上方标签查看 A 股特色数据
          </div>
        ) : loading && !activeData ? (
          <div className="flex items-center justify-center h-full gap-2 text-text-secondary text-xs">
            <Loader2 size={14} className="animate-spin" />
            正在加载…
          </div>
        ) : error && !activeData ? (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            <span className="text-xs text-down">✕ {error}</span>
            <button
              onClick={() => fetchFeature(activeTab)}
              className="text-xs text-accent hover:underline"
            >
              重试
            </button>
          </div>
        ) : activeData ? (
          <FeatureRenderer feature={activeTab} data={activeData} />
        ) : null}
      </div>
    </div>
  );
}

// ── Feature panel dispatcher ──────────────────────────────────────────────────

function FeatureRenderer({ feature, data }: { feature: AstockFeatureKey; data: AstockFeatureEnvelope }) {
  if (feature === "chip_distribution") {
    return <ChipPanel data={data.data as unknown as ChipDistributionData} rawMd={data.raw_md} />;
  }
  if (feature === "dragon_tiger") {
    return <DragonTigerPanel data={data.data as unknown as DragonTigerData} rawMd={data.raw_md} />;
  }
  if (feature === "northbound_flow") {
    return <NorthboundPanel data={data.data as unknown as NorthboundData} rawMd={data.raw_md} />;
  }
  if (feature === "concept_blocks") {
    return <ConceptPanel data={data.data as unknown as ConceptBlocksData} rawMd={data.raw_md} />;
  }
  if (feature === "profit_forecast") {
    return <ProfitForecastPanel data={data.data as unknown as ProfitForecastData} rawMd={data.raw_md} />;
  }
  if (feature === "lockup_expiry") {
    return <LockupPanel data={data.data as unknown as LockupExpiryData} rawMd={data.raw_md} />;
  }
  if (feature === "hot_stocks") {
    return <HotStockPanel data={data.data as unknown as HotStocksData} rawMd={data.raw_md} />;
  }
  if (feature === "balance_sheet" || feature === "income_statement" || feature === "cashflow") {
    return <FinancialStatementPanel feature={feature} data={data.data as unknown as FinancialStatementData} rawMd={data.raw_md} />;
  }
  if (feature === "industry_comparison") {
    return <IndustryComparisonPanel data={data.data as unknown as IndustryComparisonData} rawMd={data.raw_md} />;
  }
  if (feature === "insider_transactions") {
    return <InsiderTransactionsPanel data={data.data as unknown as InsiderTransactionsData} rawMd={data.raw_md} />;
  }
  // Phase 9: new panels
  if (feature === "block_trade_detail" || feature === "block_trade_industry" || feature === "block_trade_market_stat") {
    return <BlockTradePanel data={data.data} rawMd={data.raw_md} />;
  }
  if (feature === "dividend_bonus") {
    return <DividendBonusPanel data={data.data} rawMd={data.raw_md} />;
  }
  if (feature === "earnings_forecast" || feature === "earnings_express") {
    return <EarningsForecastPanel data={data.data} rawMd={data.raw_md} />;
  }
  if (feature === "analyst_rating") {
    return <AnalystRatingPanel data={data.data} rawMd={data.raw_md} />;
  }
  if (feature === "institutional_hold") {
    return <InstitutionalHoldPanel data={data.data} rawMd={data.raw_md} />;
  }
  // Phase 12.02: 持仓股东（一个组件三种形态）
  if (feature === "holder_num") {
    return <HolderPanel mode="num" data={data.data} rawMd={data.raw_md} />;
  }
  if (feature === "free_holders") {
    return <HolderPanel mode="free" data={data.data} rawMd={data.raw_md} />;
  }
  if (feature === "holder_increase") {
    return <HolderPanel mode="increase" data={data.data} rawMd={data.raw_md} />;
  }
  if (feature === "stock_notices") {
    return <StockNoticesPanel data={data.data} rawMd={data.raw_md} />;
  }
  if (feature === "research_reports") {
    return <ResearchReportsPanel data={data.data} rawMd={data.raw_md} />;
  }
  // 全市场数据（新股/融资融券/日历/活跃度）不在个股标签栏显示，通过「市场」页面访问
  // All other features: use MarkdownRenderer for raw_md fallback
  return (
    <div className="h-full overflow-y-auto p-3">
      {data.raw_md ? (
        <MarkdownRenderer markdown={data.raw_md} />
      ) : (
        <div className="flex items-center justify-center h-full text-text-secondary text-xs">
          暂无数据
        </div>
      )}
    </div>
  );
}
