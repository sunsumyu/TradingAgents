/**
 * FundDataPanel — 基金发行列表（对标通达信「基金数据」）。
 *
 * Tabs: 全部 / 发行中 / 将发行
 * Columns: 基金代码 | 基金简称 | 基金类型 | 最新净值 | 申购状态 | 赎回状态 | 下一开放日 | 手续费
 */

import { useState } from "react";
import type { FundPurchaseData } from "../../lib/types";
import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: FundPurchaseData;
  rawMd: string;
}

type FundTab = "all" | "issuing" | "upcoming";

const FUND_TABS: { key: FundTab; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "issuing", label: "发行中" },
  { key: "upcoming", label: "将发行" },
];

export default function FundDataPanel({ data, rawMd }: Props) {
  const [tab, setTab] = useState<FundTab>("all");

  // Structured rendering when data is available
  if (data && data.items && data.items.length > 0) {
    const items = tab === "all" ? data.items : data[tab] ?? data.items;

    return (
      <div className="h-full flex flex-col bg-[#0D1117]">
        {/* Sub-tab bar */}
        <div className="flex items-center gap-0 border-b border-[#1E222D] px-3 bg-[#131722]">
          {FUND_TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-1.5 text-[11px] transition-colors ${
                tab === t.key
                  ? "bg-[#2962FF] text-white rounded"
                  : "text-[#787B86] hover:text-[#D1D4DC]"
              }`}
            >
              {t.label}
            </button>
          ))}
          <span className="ml-auto text-[10px] text-[#4C525E] pr-2">
            共 {data.total ?? items.length} 只
          </span>
        </div>

        {/* Table */}
        <div className="flex-1 min-h-0 overflow-auto">
          <table className="w-full text-[11px] border-collapse">
            <thead className="sticky top-0 bg-[#131722] z-10">
              <tr className="border-b border-[#1E222D]">
                <th className="text-left px-2 py-1.5 text-[#4C525E] font-medium">基金代码</th>
                <th className="text-left px-2 py-1.5 text-[#4C525E] font-medium">基金简称</th>
                <th className="text-left px-2 py-1.5 text-[#4C525E] font-medium">基金类型</th>
                <th className="text-right px-2 py-1.5 text-[#4C525E] font-medium">最新净值</th>
                <th className="text-center px-2 py-1.5 text-[#4C525E] font-medium">申购</th>
                <th className="text-center px-2 py-1.5 text-[#4C525E] font-medium">赎回</th>
                <th className="text-left px-2 py-1.5 text-[#4C525E] font-medium">下一开放日</th>
                <th className="text-right px-2 py-1.5 text-[#4C525E] font-medium">手续费</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, 100).map((item: any, i: number) => {
                const subStatus = item.subscribe_status ?? item.申购状态 ?? "";
                const redStatus = item.redeem_status ?? item.赎回状态 ?? "";
                const isPaused = subStatus.includes("暂停") || redStatus.includes("暂停");
                return (
                  <tr
                    key={item.code ?? item.基金代码 ?? i}
                    className={`border-b border-[#1E222D]/40 hover:bg-[#2A2E39]/50 ${
                      isPaused ? "opacity-60" : ""
                    }`}
                  >
                    <td className="px-2 py-1 font-mono text-[#2962FF]">{item.code ?? item.基金代码 ?? ""}</td>
                    <td className="px-2 py-1 text-[#D1D4DC] truncate max-w-[180px]" title={item.name ?? item.基金简称 ?? ""}>{item.name ?? item.基金简称 ?? ""}</td>
                    <td className="px-2 py-1 text-[#787B86]">{item.type ?? item.基金类型 ?? ""}</td>
                    <td className="px-2 py-1 text-right tabular-nums text-[#D1D4DC]">{item.nav ?? item["最新净值/万份收益"] ?? "--"}</td>
                    <td className="px-2 py-1 text-center text-[10px]">
                      <span className={subStatus.includes("开放") ? "text-[#26A69A]" : subStatus.includes("暂停") ? "text-[#F23645]" : "text-[#787B86]"}>
                        {subStatus || "--"}
                      </span>
                    </td>
                    <td className="px-2 py-1 text-center text-[10px]">
                      <span className={redStatus.includes("开放") ? "text-[#26A69A]" : redStatus.includes("暂停") ? "text-[#F23645]" : "text-[#787B86]"}>
                        {redStatus || "--"}
                      </span>
                    </td>
                    <td className="px-2 py-1 text-[#787B86]">{item.next_open ?? item.下一开放日 ?? "--"}</td>
                    <td className="px-2 py-1 text-right tabular-nums text-[#D1D4DC]">{item.fee_rate ?? item.手续费 ?? "--"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        {data.timestamp && (
          <div className="text-[10px] text-[#4C525E] px-3 py-1 border-t border-[#1E222D]">
            {data.timestamp}
          </div>
        )}
      </div>
    );
  }

  // Fallback to markdown
  if (rawMd) {
    return <MarkdownRenderer markdown={rawMd} className="p-3" />;
  }

  return (
    <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
      加载中…
    </div>
  );
}
