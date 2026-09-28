/**
 * AnalystRatingPanel — 价值分析面板（分析师评级 / 目标价 / EPS 预测）。
 */

import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: Record<string, unknown>;
  rawMd: string;
}

export default function AnalystRatingPanel({ data, rawMd }: Props) {
  if (!rawMd && !data) {
    return <div className="flex items-center justify-center h-full text-[#787B86] text-xs">暂无分析师评级数据</div>;
  }

  return (
    <div className="h-full overflow-y-auto p-3">
      <div className="text-[12px] text-[#D1D4DC] font-medium mb-2 flex items-center gap-2">
        <span className="w-1 h-3.5 rounded-full bg-[#FF9800]" />
        价值分析 — 分析师评级
      </div>
      {rawMd ? <MarkdownRenderer markdown={rawMd} /> : <div className="text-[#787B86] text-xs">加载中…</div>}
    </div>
  );
}
