/**
 * PledgePanel — 股权质押面板（Phase 12.03）。
 *
 * 三个子页签，数据来自东财 CSDC 质押报表：
 *   - 市场（pledge_market）：质押公司数/股数/市值 + 沪深300 参考
 *   - 行业（pledge_industry）：按平均质押比例降序
 *   - 个股（pledge_stock）：全市场质押比例榜（降序）
 *
 * 经 `FeatureDataTable` 渲染（排序 / 分页 / raw 降级内置）。
 */

import { useState } from "react";
import { FeatureDataTable } from "../shared/GenericDataTable";
import type { FeatureColumn } from "../../lib/types";

interface Props {
  market?: Record<string, unknown> | null;
  industry?: Record<string, unknown> | null;
  stock?: Record<string, unknown> | null;
  marketRawMd?: string;
  industryRawMd?: string;
  stockRawMd?: string;
  loading?: boolean;
}

const MARKET_COLUMNS: FeatureColumn[] = [
  { key: "trade_date", label: "日期", unit: "date", format: "date" },
  { key: "pledge_co_num", label: "质押公司数", unit: "count", format: "int" },
  { key: "pledged_shares_yi", label: "质押股数(亿股)", unit: "亿股", format: "float2" },
  { key: "pledge_mv_yi", label: "质押市值(亿元)", unit: "亿元", format: "float2" },
  { key: "csi300_index", label: "沪深300", unit: "count", format: "float2" },
  { key: "csi300_chg", label: "涨跌幅", unit: "percent", format: "float2" },
];

const INDUSTRY_COLUMNS: FeatureColumn[] = [
  { key: "industry", label: "行业", unit: "text", format: "text" },
  { key: "avg_pledge_ratio", label: "平均质押比例", unit: "percent", format: "float2" },
  { key: "pledge_mv_yi", label: "质押市值(亿元)", unit: "亿元", format: "float2" },
  { key: "pledged_shares_yi", label: "质押股数(亿股)", unit: "亿股", format: "float2" },
];

const STOCK_COLUMNS: FeatureColumn[] = [
  { key: "trade_date", label: "日期", unit: "date", format: "date" },
  { key: "code", label: "代码", unit: "text", format: "text" },
  { key: "name", label: "简称", unit: "text", format: "text" },
  { key: "industry", label: "行业", unit: "text", format: "text" },
  { key: "pledge_ratio", label: "质押比例", unit: "percent", format: "float2" },
  { key: "pledge_deal_num", label: "质押笔数", unit: "count", format: "int" },
  { key: "pledge_mv_yi", label: "质押市值(亿元)", unit: "亿元", format: "float2" },
];

type SubTab = "market" | "industry" | "stock";

export default function PledgePanel({
  market,
  industry,
  stock,
  marketRawMd = "",
  industryRawMd = "",
  stockRawMd = "",
  loading = false,
}: Props) {
  const [subTab, setSubTab] = useState<SubTab>("market");

  const conf: Record<SubTab, { data?: Record<string, unknown> | null; rawMd: string; cols: FeatureColumn[]; empty: string }> = {
    market: { data: market, rawMd: marketRawMd, cols: MARKET_COLUMNS, empty: "暂无市场质押数据" },
    industry: { data: industry, rawMd: industryRawMd, cols: INDUSTRY_COLUMNS, empty: "暂无行业质押数据" },
    stock: { data: stock, rawMd: stockRawMd, cols: STOCK_COLUMNS, empty: "暂无个股质押数据" },
  };
  const c = conf[subTab];

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center gap-3 px-3 pt-2">
        <div className="text-[12px] text-text-primary font-medium flex items-center gap-2">
          <span className="w-1 h-3.5 rounded-full bg-[#FF9800]" />
          股权质押
        </div>
        <div className="flex gap-1">
          {(
            [
              ["market", "市场"],
              ["industry", "行业"],
              ["stock", "个股"],
            ] as [SubTab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setSubTab(key)}
              className={`px-2 py-0.5 text-[11px] rounded transition-colors ${
                subTab === key
                  ? "bg-bg-hover text-text-primary"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <FeatureDataTable
          columns={c.cols}
          data={c.data ?? undefined}
          rawMd={c.rawMd}
          loading={loading}
          emptyText={c.empty}
        />
      </div>
    </div>
  );
}
