/**
 * InsiderTransactionsPanel — Timeline-style section cards for
 * shareholder research data (mootdx F10).
 *
 * Each section from the parsed data renders as a card with title + content.
 * Falls back to raw_md rendering when no structured sections exist.
 */

import type { InsiderTransactionsData } from "../../lib/types";

interface Props {
  data: InsiderTransactionsData;
  rawMd: string;
}

export default function InsiderTransactionsPanel({ data, rawMd }: Props) {
  const { sections, raw_text } = data;

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!sections.length && !raw_text) {
    return (
      <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
        暂无股东动向数据
      </div>
    );
  }

  // ── Structured sections ───────────────────────────────────────────────────
  if (sections.length > 0) {
    return (
      <div className="h-full overflow-y-auto p-3 space-y-2">
        {/* Timeline dot + line */}
        <div className="relative pl-4">
          {/* Vertical line */}
          <div className="absolute left-1.5 top-1 bottom-1 w-px bg-[#2B2B43]" />

          {sections.map((section, i) => (
            <div key={i} className="relative mb-3 last:mb-0">
              {/* Timeline dot */}
              <div
                className="absolute -left-4 top-1.5 w-2.5 h-2.5 rounded-full border-2 border-[#2962FF] bg-[#131722]"
              />

              {/* Card */}
              <div className="bg-[#1E222D] rounded border border-[#363A45] p-2.5 ml-2">
                <div className="text-[11px] font-medium text-[#2962FF] mb-1.5">
                  {section.title}
                </div>
                <pre className="text-[10px] text-[#787B86] whitespace-pre-wrap leading-relaxed font-mono">
                  {section.content}
                </pre>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Fallback: raw markdown ────────────────────────────────────────────────
  return (
    <div className="h-full overflow-y-auto">
      <pre className="text-[11px] text-[#787B86] p-3 whitespace-pre-wrap leading-relaxed">
        {raw_text || rawMd}
      </pre>
    </div>
  );
}
