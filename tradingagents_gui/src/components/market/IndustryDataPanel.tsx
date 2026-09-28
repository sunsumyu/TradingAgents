/**
 * IndustryDataPanel — 行业数据（对标通达信「行业数据」）。
 *
 * Layout:
 * - Left: category tree (能源/钢铁/有色/…)
 * - Right: commodity prices + related companies
 */

import { useState } from "react";
import type { IndustryDataOverview } from "../../lib/types";
import { formatDateShort } from "../../lib/dateFormat";
import { useLanguage } from "../../lib/useLanguage";
import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: IndustryDataOverview;
  rawMd: string;
}

function signColor(v: number): string {
  return v > 0 ? "text-[#F23645]" : v < 0 ? "text-[#26A69A]" : "text-[#787B86]";
}

export default function IndustryDataPanel({ data, rawMd }: Props) {
  const lang = useLanguage();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // Structured rendering
  if (data) {
    const categories = data.list?.categories ?? [];
    const industries = data.list?.industries ?? [];
    const commodities = data.commodity?.commodities ?? [];

    return (
      <div className="h-full flex bg-[#0D1117]">
        {/* Left: category tree */}
        <div className="w-[140px] flex-shrink-0 border-r border-[#1E222D] overflow-y-auto bg-[#131722]">
          <div className="px-2 py-1.5 text-[11px] text-[#787B86] font-medium border-b border-[#1E222D]">
            行业分类
          </div>
          {categories.map((cat: string) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
              className={`w-full text-left px-2 py-1 text-[11px] transition-colors ${
                selectedCategory === cat
                  ? "bg-[#2962FF]/20 text-[#2962FF] font-medium"
                  : "text-[#D1D4DC] hover:bg-[#2A2E39]/50"
              }`}
            >
              <span className="mr-1">{selectedCategory === cat ? "▶" : "▷"}</span>
              {cat}
            </button>
          ))}
        </div>

        {/* Right: data area */}
        <div className="flex-1 min-w-0 flex flex-col overflow-y-auto">
          {/* Commodity prices */}
          {commodities.length > 0 && (
            <div className="border-b border-[#1E222D]">
              <div className="px-3 py-1.5 text-[11px] text-[#787B86] font-medium bg-[#131722]">
                商品价格
              </div>
              {commodities.map((c: any) => (
                <div key={c.name} className="px-3 py-2">
                  <div className="flex items-baseline gap-3 mb-2">
                    <span className="text-[13px] text-[#F23645] font-bold">{c.name}</span>
                    <span className="text-[11px] text-[#787B86]">{c.unit}</span>
                    <span className="text-[14px] tabular-nums text-[#D1D4DC]">{c.price}</span>
                    <span className={`text-[11px] tabular-nums ${signColor(c.change)}`}>
                      {c.change > 0 ? "+" : ""}{c.change.toFixed(2)} ({c.change_pct > 0 ? "+" : ""}{c.change_pct.toFixed(2)}%)
                    </span>
                  </div>
                  {/* Mini history table */}
                  {c.history && c.history.length > 0 && (
                    <table className="w-full text-[10px]">
                      <thead>
                        <tr className="border-b border-[#1E222D]">
                          <th className="text-left py-0.5 text-[#4C525E]">日期</th>
                          <th className="text-right py-0.5 text-[#4C525E]">价格</th>
                          <th className="text-right py-0.5 text-[#4C525E]">涨跌</th>
                          <th className="text-right py-0.5 text-[#4C525E]">涨跌幅(%)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {c.history.slice(0, 10).map((h: any, i: number) => (
                          <tr key={i} className="border-b border-[#1E222D]/30">
                            <td className="py-0.5 text-[#787B86]">{formatDateShort(h.date, lang)}</td>
                            <td className="py-0.5 text-right tabular-nums text-[#D1D4DC]">{h.price}</td>
                            <td className={`py-0.5 text-right tabular-nums ${signColor(h.change)}`}>
                              {h.change > 0 ? "+" : ""}{h.change.toFixed(2)}
                            </td>
                            <td className={`py-0.5 text-right tabular-nums ${signColor(h.change_pct)}`}>
                              {h.change_pct > 0 ? "+" : ""}{h.change_pct.toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Industry list */}
          {industries.length > 0 && (
            <div className="flex-1">
              <div className="px-3 py-1.5 text-[11px] text-[#787B86] font-medium bg-[#131722] border-b border-[#1E222D]">
                行业板块 ({industries.length})
              </div>
              <table className="w-full text-[11px] table-fixed">
                <thead className="sticky top-0 bg-[#131722] z-10">
                  <tr className="border-b border-[#1E222D]">
                    <th className="w-[20%] text-left px-2 py-1 text-[#4C525E] font-medium">板块名称</th>
                    <th className="w-[20%] text-right px-2 py-1 text-[#4C525E] font-medium">涨跌幅</th>
                    <th className="w-[20%] text-right px-2 py-1 text-[#4C525E] font-medium">总市值</th>
                    <th className="w-[20%] text-right px-2 py-1 text-[#4C525E] font-medium">换手率</th>
                    <th className="w-[20%] text-right px-2 py-1 text-[#4C525E] font-medium">涨/跌</th>
                  </tr>
                </thead>
                <tbody>
                  {industries.slice(0, 50).map((item: any, i: number) => (
                    <tr key={item.code ?? i} className="border-b border-[#1E222D]/40 hover:bg-[#2A2E39]/50">
                      <td className="px-2 py-1 text-[#D1D4DC] truncate">{item.name}</td>
                      <td className={`px-2 py-1 text-right tabular-nums ${signColor(item.change_pct)}`}>
                        {item.change_pct == null
                          ? "--"
                          : `${item.change_pct > 0 ? "+" : ""}${item.change_pct.toFixed(2)}%`}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-[#787B86]">
                        {item.total_market_cap ? (item.total_market_cap / 1e8).toFixed(0) + "亿" : "--"}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-[#787B86]">
                        {item.turnover_rate ? item.turnover_rate.toFixed(2) + "%" : "--"}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums">
                        <span className="text-[#F23645]">{item.up_count ?? 0}</span>
                        <span className="text-[#4C525E]">/</span>
                        <span className="text-[#26A69A]">{item.down_count ?? 0}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data.list?.timestamp && (
            <div className="text-[10px] text-[#4C525E] px-3 py-1 border-t border-[#1E222D]">
              {data.list.timestamp}
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
