/**
 * FundFlowPanel — 板块资金流面板（Phase 12.01）。
 *
 * 行业 / 概念两个子页签，数据来自东财 datacenter 资金流报表
 * （`industry_fund_flow` / `concept_fund_flow`，某交易日主力净流入排名）。
 * 经 `FeatureDataTable` 渲染（工单 05 通用表）：排序 / 分页 / raw 降级内置。
 */

import { useState } from "react";
import { FeatureDataTable } from "../shared/GenericDataTable";
import type { FeatureColumn } from "../../lib/types";

interface Props {
  industry?: Record<string, unknown> | null;
  concept?: Record<string, unknown> | null;
  industryRawMd?: string;
  conceptRawMd?: string;
  loading?: boolean;
}

const COLUMNS: FeatureColumn[] = [
  { key: "board_name", label: "板块", unit: "text", format: "text" },
  { key: "change_pct", label: "涨跌幅", unit: "percent", format: "float2" },
  { key: "net_inflow_yi", label: "主力净流入(亿)", unit: "亿元", format: "float2" },
  { key: "net_inflow_pct", label: "主力净占比", unit: "percent", format: "float2" },
  { key: "super_deal_yi", label: "超大单(亿)", unit: "亿元", format: "float2" },
  { key: "big_deal_yi", label: "大单(亿)", unit: "亿元", format: "float2" },
  { key: "mid_deal_yi", label: "中单(亿)", unit: "亿元", format: "float2" },
  { key: "small_deal_yi", label: "小单(亿)", unit: "亿元", format: "float2" },
  { key: "lead_stock", label: "领涨股", unit: "text", format: "text" },
];

type SubTab = "industry" | "concept";

export default function FundFlowPanel({
  industry,
  concept,
  industryRawMd = "",
  conceptRawMd = "",
  loading = false,
}: Props) {
  const [subTab, setSubTab] = useState<SubTab>("industry");

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center gap-3 px-3 pt-2">
        <div className="text-[12px] text-text-primary font-medium flex items-center gap-2">
          <span className="w-1 h-3.5 rounded-full bg-[#2962FF]" />
          板块资金流
        </div>
        <div className="flex gap-1">
          {(
            [
              ["industry", "行业"],
              ["concept", "概念"],
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
        {subTab === "industry" ? (
          <FeatureDataTable
            columns={COLUMNS}
            data={industry ?? undefined}
            rawMd={industryRawMd}
            loading={loading}
            emptyText="暂无行业资金流数据"
          />
        ) : (
          <FeatureDataTable
            columns={COLUMNS}
            data={concept ?? undefined}
            rawMd={conceptRawMd}
            loading={loading}
            emptyText="暂无概念资金流数据"
          />
        )}
      </div>
    </div>
  );
}
