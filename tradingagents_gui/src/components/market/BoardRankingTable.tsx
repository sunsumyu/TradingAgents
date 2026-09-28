/**
 * BoardRankingTable — 板块排行表（行业/概念/风格/地区 Tab 切换）。
 */

import { useState } from "react";
import type { BoardRankingItem, BoardType } from "../../lib/types";

interface Props {
  boards: Record<string, BoardRankingItem[]>;
  onBoardClick?: (code: string) => void;
}

const TABS: { key: BoardType; label: string }[] = [
  { key: "industry", label: "行业" },
  { key: "concept", label: "概念" },
  { key: "style", label: "风格" },
  { key: "region", label: "地区" },
];

function signBg(v: number): string {
  return v > 0 ? "bg-[#F23645]/10 text-[#F23645]" : v < 0 ? "bg-[#26A69A]/10 text-[#26A69A]" : "text-[#787B86]";
}

export default function BoardRankingTable({ boards, onBoardClick }: Props) {
  const [activeTab, setActiveTab] = useState<BoardType>("industry");
  const items = boards[activeTab] ?? [];

  return (
    <div className="h-full flex flex-col">
      {/* Tab bar */}
      <div className="flex items-center gap-0 border-b border-[#1E222D] px-2">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-3 py-1.5 text-[11px] transition-colors ${
              activeTab === tab.key
                ? "text-[#2962FF] border-b-2 border-[#2962FF] font-medium"
                : "text-[#787B86] hover:text-[#D1D4DC]"
            }`}
          >
            {tab.label}
          </button>
        ))}
        <span className="ml-auto text-[10px] text-[#4C525E]">{items.length} 个板块</span>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-[11px]">
          <thead className="sticky top-0 bg-[#131722]">
            <tr className="border-b border-[#1E222D]">
              <th className="px-2 py-1 text-left text-[10px] text-[#4C525E] font-medium">#</th>
              <th className="px-2 py-1 text-left text-[10px] text-[#4C525E] font-medium">板块</th>
              <th className="px-2 py-1 text-right text-[10px] text-[#4C525E] font-medium">涨幅%</th>
              <th className="px-2 py-1 text-right text-[10px] text-[#4C525E] font-medium">现价</th>
              <th className="px-2 py-1 text-right text-[10px] text-[#4C525E] font-medium">涨</th>
              <th className="px-2 py-1 text-right text-[10px] text-[#4C525E] font-medium">跌</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, i) => (
              <tr
                key={item.code}
                className="border-b border-[#1E222D]/60 hover:bg-[#2A2E39]/50 cursor-pointer"
                onClick={() => onBoardClick?.(item.code)}
              >
                <td className="px-2 py-1 text-right text-[#4C525E]">{i + 1}</td>
                <td className="px-2 py-1 text-left text-[#D1D4DC] truncate max-w-[100px]">{item.name}</td>
                <td className={`px-2 py-1 text-right tabular-nums font-medium ${signBg(item.change_pct).split(" ").slice(-1)[0]}`}>
                  {item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
                </td>
                <td className="px-2 py-1 text-right tabular-nums text-[#D1D4DC]">{item.price.toFixed(2)}</td>
                <td className="px-2 py-1 text-right tabular-nums text-[#F23645]">{item.up_count}</td>
                <td className="px-2 py-1 text-right tabular-nums text-[#26A69A]">{item.down_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
