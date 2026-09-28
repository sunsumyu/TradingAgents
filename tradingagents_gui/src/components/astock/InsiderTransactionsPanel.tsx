/**
 * InsiderTransactionsPanel — Timeline-style section cards for
 * shareholder research data (mootdx F10).
 *
 * Each section from the parsed data renders as a card with title + content.
 * Falls back to raw_md rendering when no structured sections exist.
 */

import type { InsiderTransactionsData } from "../../lib/types";
import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data: InsiderTransactionsData;
  rawMd: string;
}

export default function InsiderTransactionsPanel({ data, rawMd }: Props) {
  const { sections = [], raw_text = "" } = data ?? ({} as InsiderTransactionsData);

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!sections.length && !raw_text) {
    return (
      <div className="flex items-center justify-center h-full text-text-secondary text-xs">
        暂无股东动向数据
      </div>
    );
  }

  // ── Structured sections ───────────────────────────────────────────────────
  if (sections.length > 0) {
    return (
      <div className="h-full overflow-y-auto p-4 space-y-3">
        {/* Timeline dot + line */}
        <div className="relative pl-5">
          {/* Vertical line */}
          <div className="absolute left-2 top-2 bottom-2 w-px bg-gradient-to-b from-accent via-accent/50 to-transparent" />

          {sections.map((section, i) => (
            <div key={i} className="relative mb-4 last:mb-0">
              {/* Timeline dot */}
              <div className="absolute -left-5 top-2 w-3 h-3 rounded-full border-2 border-accent bg-bg-secondary shadow-glow-accent-sm" />

              {/* Card */}
              <div className="bg-bg-secondary rounded-lg border border-line p-3 ml-3 hover:border-accent/30 transition-colors">
                <div className="text-[12px] font-semibold text-accent-light mb-2">
                  {section.title}
                </div>
                <MarkdownRenderer markdown={section.content} />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Fallback: raw markdown ────────────────────────────────────────────────
  return (
    <div className="h-full overflow-y-auto p-4">
      <MarkdownRenderer markdown={rawMd || raw_text || ""} className="p-3" />
    </div>
  );
}
