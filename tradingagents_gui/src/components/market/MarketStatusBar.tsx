/**
 * MarketStatusBar — 底部市场宽度状态栏。
 */

import type { MarketBreadth } from "../../lib/types";

interface Props {
  breadth: MarketBreadth;
  timestamp?: string;
}

export default function MarketStatusBar({ breadth, timestamp }: Props) {
  const { total, up_count, down_count, flat_count, total_amount_yi } = breadth;

  return (
    <div className="flex items-center gap-4 px-3 py-1.5 bg-[#0D1117] border-t border-[#1E222D] text-[11px]">
      {timestamp && <span className="text-[#4C525E]">{timestamp}</span>}
      <span className="text-[#787B86]">
        总成交额: <span className="text-[#D1D4DC] font-medium">{total_amount_yi.toFixed(0)}亿</span>
      </span>
      <span className="text-[#F23645]">
        上涨: <span className="font-medium">{up_count}</span>
      </span>
      <span className="text-[#26A69A]">
        下跌: <span className="font-medium">{down_count}</span>
      </span>
      <span className="text-[#787B86]">
        平盘: <span className="font-medium">{flat_count}</span>
      </span>
      <span className="text-[#4C525E] ml-auto">
        共 {total} 只
      </span>
    </div>
  );
}
