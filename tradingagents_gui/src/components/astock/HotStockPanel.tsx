/**
 * HotStockPanel — hot stocks ranking with topic attribution.
 *
 * Scrollable table: rank, ticker, name, change%, turnover, volume, topics.
 * Topics rendered as colored pills.
 */

import type { HotStocksData } from "../../lib/types";
import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data: HotStocksData;
  rawMd: string;
}

export default function HotStockPanel({ data, rawMd }: Props) {
  const { items = [], total = 0 } = data ?? ({} as HotStocksData);

  if (!items.length) {
    return (
      <div className="h-full overflow-y-auto">
        {rawMd ? (
          <MarkdownRenderer markdown={rawMd} className="p-3" />
        ) : (
          <div className="flex items-center justify-center h-full text-text-secondary text-xs">
            暂无数据
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="text-[12px] text-text-secondary mb-3 font-medium">
        人气榜 · 共 {total} 只
      </div>
      <div className="bg-bg-secondary rounded-lg border border-line overflow-hidden">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-line">
              <th className="text-left px-3 py-2 text-text-secondary font-medium w-8">#</th>
              <th className="text-left px-3 py-2 text-text-secondary font-medium">代码</th>
              <th className="text-left px-3 py-2 text-text-secondary font-medium">名称</th>
              <th className="text-right px-3 py-2 text-text-secondary font-medium">涨跌%</th>
              <th className="text-right px-3 py-2 text-text-secondary font-medium">换手%</th>
              <th className="text-right px-3 py-2 text-text-secondary font-medium">成交额(万)</th>
              <th className="text-left px-3 py-2 text-text-secondary font-medium">题材</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => (
              <tr key={item.ticker} className="border-b border-line/50 last:border-0 hover:bg-bg-hover/50 transition-colors">
                <td className="px-3 py-2 text-text-muted tabular-nums">{idx + 1}</td>
                <td className="px-3 py-2 text-text-secondary tabular-nums font-mono">{item.ticker}</td>
                <td className="px-3 py-2 text-text-primary font-medium">{item.name}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className={item.change_pct != null && item.change_pct >= 0 ? "text-down" : "text-up"}>
                    {item.change_pct != null ? `${item.change_pct >= 0 ? "+" : ""}${item.change_pct.toFixed(2)}%` : "—"}
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-text-secondary">
                  {item.turnover_rate != null ? `${item.turnover_rate.toFixed(2)}%` : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-text-secondary">
                  {item.volume_wan != null ? item.volume_wan.toLocaleString() : "—"}
                </td>
                <td className="px-3 py-2 max-w-[200px]">
                  {item.topics ? (
                    <div className="flex flex-wrap gap-1">
                      {item.topics.split("+").filter(Boolean).map((t) => (
                        <span
                          key={t}
                          className="px-1.5 py-0.5 text-[10px] rounded bg-accent/10 text-accent-light whitespace-nowrap"
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
