/**
 * BlockTradePanel — 大宗交易面板（明细表 + 行业分布图 + 大盘统计图）。
 */

import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: Record<string, unknown>;
  rawMd: string;
}

export default function BlockTradePanel({ rawMd }: Props) {
  if (!rawMd) {
    return <div className="flex items-center justify-center h-full text-[#787B86] text-xs">暂无大宗交易数据</div>;
  }

  return (
    <div className="h-full overflow-y-auto p-3">
      <div className="text-[12px] text-[#D1D4DC] font-medium mb-2 flex items-center gap-2">
        <span className="w-1 h-3.5 rounded-full bg-[#2962FF]" />
        大宗交易
      </div>
      <MarkdownRenderer markdown={rawMd} />
    </div>
  );
}
