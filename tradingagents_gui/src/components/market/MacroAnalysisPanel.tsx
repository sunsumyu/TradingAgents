/**
 * MacroAnalysisPanel — 宏观分析（对标通达信「宏观分析」）。
 *
 * Layout:
 * - Left: category list (GDP/就业保障/居民生活/…)
 * - Right: GDP trend chart placeholder + quarterly data tables
 */

import { useState } from "react";
import type { FeatureColumn, MacroAnalysisData } from "../../lib/types";
import GenericDataTable from "../shared/GenericDataTable";
import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: MacroAnalysisData;
  rawMd: string;
  /** Phase 13 批次：macro_cpi 结构化数据 {items:[{date,value,prev}]} */
  cpiData?: Record<string, unknown>;
  /** Phase 13 批次：macro_pmi 结构化数据 {items:[{quarter,index,yoy,mom}]} */
  pmiData?: Record<string, unknown>;
}

const CPI_COLUMNS: FeatureColumn[] = [
  { key: "date", label: "月份", unit: "date", format: "date" },
  { key: "value", label: "CPI 同比", unit: "percent", format: "float2" },
  { key: "prev", label: "前值", unit: "percent", format: "float2" },
];

const PMI_COLUMNS: FeatureColumn[] = [
  { key: "quarter", label: "季度", unit: "text", format: "text" },
  { key: "index", label: "景气指数", unit: "count", format: "float2" },
  { key: "yoy", label: "同比", unit: "percent", format: "float2" },
  { key: "mom", label: "环比", unit: "percent", format: "float2" },
];

const asItems = (data?: Record<string, unknown>): Record<string, unknown>[] =>
  Array.isArray((data as { items?: unknown })?.items)
    ? ((data as { items: Record<string, unknown>[] }).items)
    : [];

type MacroTab = "current" | "yoy" | "cumulative" | "cumulative_yoy";

const GDP_TABS: { key: MacroTab; label: string }[] = [
  { key: "current", label: "当期值" },
  { key: "yoy", label: "当期同比增长" },
  { key: "cumulative", label: "累计值" },
  { key: "cumulative_yoy", label: "累计同比增长" },
];

const MACRO_CATS = [
  "GDP", "就业保障", "居民生活", "财政收支", "物价指数",
  "景气指数", "工业经济", "消费", "投资", "对外经济",
  "银行货币", "证券保险", "运输邮电", "能源生产",
  "世界经济", "初级产品",
];

function fmtYi(v: number): string {
  if (!v) return "--";
  return v.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

export default function MacroAnalysisPanel({ data, rawMd, cpiData, pmiData }: Props) {
  const [selectedCat, setSelectedCat] = useState("GDP");
  const [gdpTab, setGdpTab] = useState<MacroTab>("current");
  const [structTab, setStructTab] = useState<"current" | "cumulative">("current");

  // Structured rendering
  if (data) {
    const gdp = data.gdp;
    const categories = data.categories?.categories ?? MACRO_CATS;

    return (
      <div className="h-full flex bg-[#0D1117]">
        {/* Left: category list */}
        <div className="w-[120px] flex-shrink-0 border-r border-[#1E222D] overflow-y-auto bg-[#131722]">
          <div className="px-2 py-1.5 text-[11px] text-[#787B86] font-medium border-b border-[#1E222D]">
            中国
          </div>
          {categories.map((cat: string) => (
            <button
              key={cat}
              onClick={() => setSelectedCat(cat)}
              className={`w-full text-left px-3 py-1 text-[11px] transition-colors ${
                selectedCat === cat
                  ? "bg-[#B71C1C] text-white font-medium"
                  : "text-[#D1D4DC] hover:bg-[#2A2E39]/50"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Right: data area */}
        <div className="flex-1 min-w-0 flex flex-col overflow-y-auto">
          {/* GDP Trend Section */}
          <div className="border-b border-[#1E222D]">
            <div className="flex items-center justify-between px-3 py-1.5 bg-[#131722]">
              <span className="text-[12px] text-[#B71C1C] font-bold">国内生产总值趋势</span>
              <div className="flex items-center gap-0">
                {GDP_TABS.map((t) => (
                  <button
                    key={t.key}
                    onClick={() => setGdpTab(t.key)}
                    className={`px-2 py-0.5 text-[10px] transition-colors ${
                      gdpTab === t.key
                        ? "bg-[#B71C1C] text-white rounded"
                        : "text-[#787B86] hover:text-[#D1D4DC]"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Chart placeholder (TDX shows line chart) */}
            <div className="h-[180px] flex items-center justify-center text-[#4C525E] text-[11px] border-b border-[#1E222D]">
               国内生产总值趋势图（{gdpTab === "current" ? "当期值" : gdpTab === "yoy" ? "同比增长" : gdpTab === "cumulative" ? "累计值" : "累计同比增长"}）
              {gdp?.trend && gdp.trend.length > 0 && (
                <span className="ml-2">
                  最新：{fmtYi(gdp.trend[0].gdp)} 亿元
                </span>
              )}
            </div>

            {/* GDP data table */}
            {gdp?.trend && gdp.trend.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-[10px] table-fixed">
                  <thead className="sticky top-0 bg-[#131722] z-10">
                    <tr className="border-b border-[#1E222D]">
                      <th className="w-[100px] text-left px-2 py-1 text-[#4C525E] font-medium">季度</th>
                      {gdp.trend.slice(0, 8).map((q: any, i: number) => (
                        <th key={i} className="text-right px-1 py-1 text-[#4C525E] font-medium">
                          {q.quarter}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-[#1E222D]/30">
                      <td className="px-2 py-1 text-[#B71C1C] font-medium">全国(亿元)</td>
                      {gdp.trend.slice(0, 8).map((q: any, i: number) => (
                        <td key={i} className="px-1 py-1 text-right tabular-nums text-[#B71C1C]">
                          {fmtYi(q.gdp)}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b border-[#1E222D]/30">
                      <td className="px-2 py-1 text-[#787B86]">第一产业(亿元)</td>
                      {gdp.trend.slice(0, 8).map((q: any, i: number) => (
                        <td key={i} className="px-1 py-1 text-right tabular-nums text-[#787B86]">
                          {fmtYi(q.primary)}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b border-[#1E222D]/30">
                      <td className="px-2 py-1 text-[#787B86]">第二产业(亿元)</td>
                      {gdp.trend.slice(0, 8).map((q: any, i: number) => (
                        <td key={i} className="px-1 py-1 text-right tabular-nums text-[#787B86]">
                          {fmtYi(q.secondary)}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b border-[#1E222D]/30">
                      <td className="px-2 py-1 text-[#787B86]">第三产业(亿元)</td>
                      {gdp.trend.slice(0, 8).map((q: any, i: number) => (
                        <td key={i} className="px-1 py-1 text-right tabular-nums text-[#787B86]">
                          {fmtYi(q.tertiary)}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* GDP Structure Section */}
          <div className="flex-1">
            <div className="flex items-center justify-between px-3 py-1.5 bg-[#131722]">
              <span className="text-[12px] text-[#B71C1C] font-bold">国内生产总值结构</span>
              <div className="flex items-center gap-0">
                {(["current", "cumulative"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setStructTab(t)}
                    className={`px-2 py-0.5 text-[10px] transition-colors ${
                      structTab === t
                        ? "bg-[#B71C1C] text-white rounded"
                        : "text-[#787B86] hover:text-[#D1D4DC]"
                    }`}
                  >
                    {t === "current" ? "当期占比" : "累计占比"}
                  </button>
                ))}
              </div>
            </div>

            {/* Structure chart placeholder */}
            <div className="h-[140px] flex items-center justify-center text-[#4C525E] text-[11px] border-b border-[#1E222D]">
              📊 国内生产总值结构图（第一/第二/第三产业占比）
            </div>

            {/* Structure data table */}
            {gdp?.structure && gdp.structure.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-[10px] table-fixed">
                  <thead className="sticky top-0 bg-[#131722] z-10">
                    <tr className="border-b border-[#1E222D]">
                      <th className="w-[100px] text-left px-2 py-1 text-[#4C525E] font-medium">季度</th>
                      {gdp.structure.slice(0, 8).map((q: any, i: number) => (
                        <th key={i} className="text-right px-1 py-1 text-[#4C525E] font-medium">
                          {q.quarter}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-[#1E222D]/30">
                      <td className="px-2 py-1 text-[#B71C1C] font-medium">第一产业占比(%)</td>
                      {gdp.structure.slice(0, 8).map((q: any, i: number) => (
                        <td key={i} className="px-1 py-1 text-right tabular-nums text-[#B71C1C]">
                          {q.primary_pct?.toFixed(2) ?? "--"}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b border-[#1E222D]/30">
                      <td className="px-2 py-1 text-[#1565C0] font-medium">第二产业占比(%)</td>
                      {gdp.structure.slice(0, 8).map((q: any, i: number) => (
                        <td key={i} className="px-1 py-1 text-right tabular-nums text-[#1565C0]">
                          {q.secondary_pct?.toFixed(2) ?? "--"}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b border-[#1E222D]/30">
                      <td className="px-2 py-1 text-[#F57F17] font-medium">第三产业占比(%)</td>
                      {gdp.structure.slice(0, 8).map((q: any, i: number) => (
                        <td key={i} className="px-1 py-1 text-right tabular-nums text-[#F57F17]">
                          {q.tertiary_pct?.toFixed(2) ?? "--"}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* CPI / PMI（Phase 13 批次结构化数据，FeatureDataTable 渲染） */}
          {asItems(cpiData).length > 0 && (
            <div className="border-t border-[#1E222D]">
              <div className="px-3 py-1.5 bg-[#131722] text-[12px] text-[#B71C1C] font-bold">
                物价指数（CPI 月率）
              </div>
              <GenericDataTable
                columns={CPI_COLUMNS}
                rows={asItems(cpiData)}
                pageSize={12}
                className="max-h-[220px] overflow-y-auto"
              />
            </div>
          )}
          {asItems(pmiData).length > 0 && (
            <div className="border-t border-[#1E222D]">
              <div className="px-3 py-1.5 bg-[#131722] text-[12px] text-[#B71C1C] font-bold">
                景气指数（PMI）
              </div>
              <GenericDataTable
                columns={PMI_COLUMNS}
                rows={asItems(pmiData)}
                pageSize={12}
                className="max-h-[220px] overflow-y-auto"
              />
            </div>
          )}

          {gdp?.timestamp && (
            <div className="text-[10px] text-[#4C525E] px-3 py-1 border-t border-[#1E222D]">
              {gdp.timestamp}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Fallback
  if (rawMd) {
    return <MarkdownRenderer markdown={rawMd} className="p-3" />;
  }

  return (
    <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
      加载中…
    </div>
  );
}
