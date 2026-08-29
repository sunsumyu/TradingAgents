/**
 * HotStockPanel — hot stocks ranking with topic attribution.
 *
 * Scrollable table: rank, ticker, name, change%, turnover, volume, topics.
 * Topics rendered as colored pills.
 */

import type { HotStocksData } from "../../lib/types";

interface Props {
  data: HotStocksData;
  rawMd: string;
}

export default function HotStockPanel({ data, rawMd }: Props) {
  const { items, total } = data;

  if (!items.length) {
    return (
      <div className="h-full overflow-y-auto">
        {rawMd ? (
          <pre className="text-[11px] text-[#787B86] p-3 whitespace-pre-wrap leading-relaxed">
            {rawMd}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
            暂无数据
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3">
      <div className="text-[11px] text-[#787B86] mb-1.5">
        人气榜 · 共 {total} 只
      </div>
      <div className="bg-[#1E222D] rounded border border-[#363A45] overflow-hidden">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="border-b border-[#363A45]">
              <th className="text-left px-2 py-1 text-[#787B86] font-medium w-6">#</th>
              <th className="text-left px-2 py-1 text-[#787B86] font-medium">代码</th>
              <th className="text-left px-2 py-1 text-[#787B86] font-medium">名称</th>
              <th className="text-right px-2 py-1 text-[#787B86] font-medium">涨跌%</th>
              <th className="text-right px-2 py-1 text-[#787B86] font-medium">换手%</th>
              <th className="text-right px-2 py-1 text-[#787B86] font-medium">成交额(万)</th>
              <th className="text-left px-2 py-1 text-[#787B86] font-medium">题材</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => (
              <tr key={item.ticker} className="border-b border-[#363A45]/50 last:border-0 hover:bg-[#2B2B43]/30">
                <td className="px-2 py-1 text-[#4C525E] tabular-nums">{idx + 1}</td>
                <td className="px-2 py-1 text-[#787B86] tabular-nums">{item.ticker}</td>
                <td className="px-2 py-1 text-[#D1D4DC] font-medium">{item.name}</td>
                <td className="px-2 py-1 text-right tabular-nums">
                  <span className={item.change_pct != null && item.change_pct >= 0 ? "text-[#F23645]" : "text-[#26A69A]"}>
                    {item.change_pct != null ? `${item.change_pct >= 0 ? "+" : ""}${item.change_pct.toFixed(2)}%` : "—"}
                  </span>
                </td>
                <td className="px-2 py-1 text-right tabular-nums text-[#787B86]">
                  {item.turnover_rate != null ? `${item.turnover_rate.toFixed(2)}%` : "—"}
                </td>
                <td className="px-2 py-1 text-right tabular-nums text-[#787B86]">
                  {item.volume_wan != null ? item.volume_wan.toLocaleString() : "—"}
                </td>
                <td className="px-2 py-1 max-w-[200px]">
                  {item.topics ? (
                    <div className="flex flex-wrap gap-0.5">
                      {item.topics.split("+").filter(Boolean).map((t) => (
                        <span
                          key={t}
                          className="px-1 py-0 text-[9px] rounded bg-[#2962FF]/10 text-[#2962FF] whitespace-nowrap"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
