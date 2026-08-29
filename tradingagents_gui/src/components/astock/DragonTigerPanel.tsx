/**
 * DragonTigerPanel — Dragon tiger board (龙虎榜) panel.
 *
 * Shows:
 * 1. Appearance records table: date / reason / net buy(万) / turnover %
 * 2. Expandable seat detail for the latest date: buy seats (red) + sell seats (green)
 * 3. Institution badge for 机构专用 seats
 * 4. Institutional activity summary line
 *
 * Empty state reuses backend "近N日未上龙虎榜" text via raw_md fallback.
 */

import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { DragonTigerAppearance, DragonTigerData, DragonTigerSeat } from "../../lib/types";

interface Props {
  data: DragonTigerData;
  rawMd: string;
}

function formatWan(v: number): string {
  if (v === 0) return "0";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(0)}`;
}

function wanColor(v: number): string {
  return v > 0 ? "text-[#F23645]" : v < 0 ? "text-[#26A69A]" : "text-[#787B86]";
}

function SeatRow({ seat }: { seat: DragonTigerSeat }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1 text-[11px]">
      <span className="flex-1 min-w-0 truncate text-[#D1D4DC]">
        {seat.name}
        {seat.is_institution && (
          <span className="ml-1 inline-block px-1 py-0.5 rounded bg-[#2962FF]/20 text-[#2962FF] text-[9px] font-medium">
            机构
          </span>
        )}
      </span>
      <span className="w-16 text-right text-[#787B86]">{seat.buy_wan.toFixed(0)}</span>
      <span className="w-16 text-right text-[#787B86]">{seat.sell_wan.toFixed(0)}</span>
      <span className={`w-16 text-right font-mono ${wanColor(seat.net_wan)}`}>
        {formatWan(seat.net_wan)}
      </span>
    </div>
  );
}

function SeatSection({ title, seats }: { title: string; seats: DragonTigerSeat[] }) {
  if (seats.length === 0) return null;
  return (
    <div className="mt-1">
      <div className="px-3 py-0.5 text-[10px] text-[#787B86] font-medium">{title}</div>
      <div className="flex items-center gap-2 px-3 py-0.5 text-[10px] text-[#4C525E] border-b border-[#1E222D]">
        <span className="flex-1">营业部</span>
        <span className="w-16 text-right">买入(万)</span>
        <span className="w-16 text-right">卖出(万)</span>
        <span className="w-16 text-right">净额(万)</span>
      </div>
      {seats.map((s, i) => (
        <SeatRow key={i} seat={s} />
      ))}
    </div>
  );
}

export default function DragonTigerPanel({ data, rawMd }: Props) {
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const appearances = data.appearances ?? [];

  // Empty state
  if (appearances.length === 0) {
    return (
      <div className="h-full overflow-y-auto">
        {rawMd ? (
          <pre className="text-[11px] text-[#787B86] p-3 whitespace-pre-wrap leading-relaxed">
            {rawMd}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
            暂无龙虎榜数据
          </div>
        )}
      </div>
    );
  }

  // Deduplicate appearances by date (same date can appear multiple times
  // for different reasons — group them)
  const grouped = new Map<string, DragonTigerAppearance[]>();
  for (const a of appearances) {
    const list = grouped.get(a.date) ?? [];
    list.push(a);
    grouped.set(a.date, list);
  }
  const uniqueDates = Array.from(grouped.keys());

  // Only show seats for the first (most recent) date
  const latestDate = uniqueDates[0];

  return (
    <div className="h-full overflow-y-auto text-[11px]">
      {/* Institutional activity summary */}
      {data.inst_buy_wan != null && data.inst_sell_wan != null && (
        <div className="px-3 py-1.5 border-b border-[#2B2B43] flex items-center gap-3 text-[#787B86]">
          <span>机构买入</span>
          <span className="text-[#F23645] font-mono">{data.inst_buy_wan.toFixed(0)}万</span>
          <span>卖出</span>
          <span className="text-[#26A69A] font-mono">{data.inst_sell_wan.toFixed(0)}万</span>
          <span>净额</span>
          <span className={`font-mono ${wanColor(data.inst_buy_wan - data.inst_sell_wan)}`}>
            {formatWan(data.inst_buy_wan - data.inst_sell_wan)}万
          </span>
        </div>
      )}

      {/* Appearance records */}
      <table className="w-full">
        <thead>
          <tr className="text-[10px] text-[#4C525E] border-b border-[#2B2B43]">
            <th className="px-3 py-1.5 text-left font-medium">日期</th>
            <th className="px-2 py-1.5 text-left font-medium">上榜原因</th>
            <th className="px-2 py-1.5 text-right font-medium">净买入(万)</th>
            <th className="px-3 py-1.5 text-right font-medium">换手率</th>
            <th className="w-6"></th>
          </tr>
        </thead>
        <tbody>
          {uniqueDates.map((dateStr, idx) => {
            const reasons = grouped.get(dateStr)!;
            const first = reasons[0];
            const isOpen = expandedRow === idx;
            const isLatest = dateStr === latestDate;
            return (
              <Fragment key={dateStr}>
                <tr
                  className={`border-b border-[#1E222D] cursor-pointer hover:bg-[#1E222D] transition-colors ${
                    isLatest ? "bg-[#1E222D]/50" : ""
                  }`}
                  onClick={() => setExpandedRow(isOpen ? null : idx)}
                >
                  <td className="px-3 py-1.5 text-[#D1D4DC] whitespace-nowrap">{dateStr}</td>
                  <td className="px-2 py-1.5 text-[#787B86] truncate max-w-[200px]">
                    {reasons.length > 1 ? `${reasons[0].reason} 等${reasons.length}条` : first.reason}
                  </td>
                  <td className={`px-2 py-1.5 text-right font-mono ${wanColor(first.net_buy_wan)}`}>
                    {formatWan(first.net_buy_wan)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-[#787B86]">
                    {first.turnover_rate != null ? `${first.turnover_rate.toFixed(1)}%` : "—"}
                  </td>
                  <td className="px-1 py-1.5 text-[#4C525E]">
                    {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  </td>
                </tr>
                {isOpen && isLatest && (
                  <tr>
                    <td colSpan={5} className="bg-[#131722] border-b border-[#2B2B43]">
                      <SeatSection title="买入席位 TOP5" seats={data.buy_seats ?? []} />
                      <SeatSection title="卖出席位 TOP5" seats={data.sell_seats ?? []} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
