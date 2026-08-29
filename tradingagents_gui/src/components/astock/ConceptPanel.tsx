/**
 * ConceptPanel — renders concept blocks + industry/region tags.
 *
 * Two sections:
 * 1. Concept tag pills (概念 only, colored, clickable feel)
 * 2. Table of all blocks with category, change%, and note
 */

import type { ConceptBlocksData, ConceptBlockItem } from "../../lib/types";

interface Props {
  data: ConceptBlocksData;
  rawMd: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  概念: "bg-[#2962FF]/15 text-[#2962FF] border-[#2962FF]/30",
  行业: "bg-[#26A69A]/15 text-[#26A69A] border-[#26A69A]/30",
  地域: "bg-[#FF9800]/15 text-[#FF9800] border-[#FF9800]/30",
};

function colorFor(cat: string) {
  return CATEGORY_COLORS[cat] ?? "bg-[#787B86]/10 text-[#787B86] border-[#787B86]/30";
}

export default function ConceptPanel({ data, rawMd }: Props) {
  const { blocks, concepts } = data;

  if (!blocks.length && !concepts.length) {
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

  // Group blocks by category
  const grouped: Record<string, ConceptBlockItem[]> = {};
  for (const b of blocks) {
    (grouped[b.category] ??= []).push(b);
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      {/* Concept pills */}
      {concepts.length > 0 && (
        <div>
          <div className="text-[11px] text-[#787B86] mb-1.5">所属概念</div>
          <div className="flex flex-wrap gap-1.5">
            {concepts.map((c) => (
              <span
                key={c}
                className="px-2 py-0.5 text-[11px] rounded-full bg-[#2962FF]/15 text-[#2962FF] border border-[#2962FF]/30"
              >
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Block tables grouped by category */}
      {Object.entries(grouped).map(([cat, items]) => (
        <div key={cat}>
          <div className="text-[11px] text-[#787B86] mb-1 flex items-center gap-1.5">
            <span className={`px-1.5 py-0 text-[10px] rounded border ${colorFor(cat)}`}>
              {cat}
            </span>
            <span>{items.length} 个</span>
          </div>
          <div className="bg-[#1E222D] rounded border border-[#363A45] overflow-hidden">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-[#363A45]">
                  <th className="text-left px-2.5 py-1 text-[#787B86] font-medium">名称</th>
                  <th className="text-right px-2.5 py-1 text-[#787B86] font-medium">涨跌%</th>
                  {items.some((b) => b.note) && (
                    <th className="text-right px-2.5 py-1 text-[#787B86] font-medium">备注</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {items.map((b) => (
                  <tr key={b.name} className="border-b border-[#363A45]/50 last:border-0">
                    <td className="px-2.5 py-1 text-[#D1D4DC]">{b.name}</td>
                    <td className="px-2.5 py-1 text-right tabular-nums">
                      {b.change_pct != null ? (
                        <span className={b.change_pct >= 0 ? "text-[#F23645]" : "text-[#26A69A]"}>
                          {b.change_pct >= 0 ? "+" : ""}
                          {b.change_pct.toFixed(2)}%
                        </span>
                      ) : (
                        <span className="text-[#4C525E]">—</span>
                      )}
                    </td>
                    {items.some((b2) => b2.note) && (
                      <td className="px-2.5 py-1 text-right text-[#787B86]">
                        {b.note ?? ""}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
