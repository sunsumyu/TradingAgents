/**
 * StockRankingPanel — 涨跌幅排行列表（上证A股/深证A股）。
 *
 * 布局约束：每个半栏在市场页仅约 160px 宽。必须用 table-fixed + 截断，
 * 否则表格按最小内容宽度撑开（>200px），涨幅表的列会压到跌幅表上形成重影。
 */

import type { StockRankingItem } from "../../lib/types";

interface Props {
  title: string;
  gainers: StockRankingItem[];
  losers: StockRankingItem[];
  onStockClick?: (code: string) => void;
}

function signColor(v: number): string {
  return v > 0 ? "text-[#F23645]" : v < 0 ? "text-[#26A69A]" : "text-[#787B86]";
}

function StockRow({ item, onClick }: { item: StockRankingItem; onClick?: (code: string) => void }) {
  return (
    <tr className="hover:bg-[#2A2E39]/50 cursor-pointer border-b border-[#1E222D]/40" onClick={() => onClick?.(item.code)}>
      <td className="w-[38%] px-1 py-1.5 text-left font-mono text-[11px] text-[#2962FF] hover:underline whitespace-nowrap overflow-hidden">{item.code}</td>
      <td className="px-1 py-1.5 text-left text-[11px] text-[#D1D4DC] truncate" title={item.name}>{item.name}</td>
      <td className={`w-[30%] px-1 py-1.5 text-right text-[11px] tabular-nums whitespace-nowrap overflow-hidden ${signColor(item.change_pct)}`}>
        {item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
      </td>
    </tr>
  );
}

function RankingSection({ title, items, onClick }: { title: string; items: StockRankingItem[]; onClick?: (code: string) => void }) {
  return (
    <div>
      <div className="text-[11px] text-[#787B86] font-medium mb-1 px-2">{title}</div>
      <table className="w-full table-fixed text-[11px]">
        <thead>
          <tr className="border-b border-[#1E222D]">
            <th className="w-[38%] px-1 py-0.5 text-left text-[10px] text-[#4C525E] font-medium">代码</th>
            <th className="px-1 py-0.5 text-left text-[10px] text-[#4C525E] font-medium overflow-hidden">名称</th>
            <th className="w-[30%] px-1 py-0.5 text-right text-[10px] text-[#4C525E] font-medium">涨跌幅</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <StockRow key={item.code} item={item} onClick={onClick} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function StockRankingPanel({ title, gainers, losers, onStockClick }: Props) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="text-[12px] text-[#D1D4DC] font-medium px-2 py-1.5 border-b border-[#1E222D] sticky top-0 bg-[#131722] z-10">{title}</div>
      <div className="flex min-h-0">
        <div className="flex-1 min-w-0 overflow-hidden border-r border-[#1E222D]">
          <RankingSection title="涨幅" items={gainers} onClick={onStockClick} />
        </div>
        <div className="flex-1 min-w-0 overflow-hidden">
          <RankingSection title="跌幅" items={losers} onClick={onStockClick} />
        </div>
      </div>
    </div>
  );
}
