/**
 * DividendBonusPanel — 增发送配面板（分红送转明细表）。
 */

import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: Record<string, unknown>;
  rawMd: string;
}

export default function DividendBonusPanel({ data, rawMd }: Props) {
  if (!rawMd && !data) {
    return <div className="flex items-center justify-center h-full text-[#787B86] text-xs">暂无增发送配数据</div>;
  }

  return (
    <div className="h-full overflow-y-auto p-3">
      <div className="text-[12px] text-[#D1D4DC] font-medium mb-2 flex items-center gap-2">
        <span className="w-1 h-3.5 rounded-full bg-[#26A69A]" />
        增发送配（分红送转）
      </div>
      {rawMd ? <MarkdownRenderer markdown={rawMd} /> : <div className="text-[#787B86] text-xs">加载中…</div>}
    </div>
  );
}
