/**
 * IndustryChainPanel — 产业链平台（对标通达信「产业链」）。
 *
 * Layout:
 * - Left: category tree (化工/有色/建材/…)
 * - Right: card grids for 最热产业链 / 最新产业链 / 全部产业链
 */

import { useState } from "react";
import type { IndustryChainData } from "../../lib/types";
import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: IndustryChainData;
  rawMd: string;
}

type ChainSection = "hot" | "new" | "all";

const SECTIONS: { key: ChainSection; label: string }[] = [
  { key: "hot", label: "最热产业链" },
  { key: "new", label: "最新产业链" },
  { key: "all", label: "全部产业链" },
];

function signColor(v: number): string {
  return v > 0 ? "text-[#F23645]" : v < 0 ? "text-[#26A69A]" : "text-[#787B86]";
}

export default function IndustryChainPanel({ data, rawMd }: Props) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [section, setSection] = useState<ChainSection>("hot");

  // Structured rendering
  if (data) {
    const categories = data.categories?.categories ?? {};
    const chains = data.chains;
    const currentChains = chains?.[section] ?? [];
    const categoryKeys = Object.keys(categories);

    return (
      <div className="h-full flex bg-[#0D1117]">
        {/* Left: category tree */}
        <div className="w-[160px] flex-shrink-0 border-r border-[#1E222D] overflow-y-auto bg-[#131722]">
          <div className="px-2 py-1.5 text-[11px] text-[#787B86] font-medium border-b border-[#1E222D]">
            全部产业链
          </div>
          {categoryKeys.map((cat) => (
            <div key={cat}>
              <button
                onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                className={`w-full text-left px-2 py-1 text-[11px] transition-colors ${
                  selectedCategory === cat
                    ? "bg-[#2962FF]/20 text-[#2962FF] font-medium"
                    : "text-[#D1D4DC] hover:bg-[#2A2E39]/50"
                }`}
              >
                <span className="mr-1">{selectedCategory === cat ? "▼" : "▶"}</span>
                {cat}
                <span className="ml-auto text-[10px] text-[#4C525E]">
                  {(categories[cat] as string[])?.length > 0 ? "☆" : ""}
                </span>
              </button>
              {selectedCategory === cat && (
                <div className="pl-4">
                  {(categories[cat] as string[])?.map((sub: string) => (
                    <div
                      key={sub}
                      className="px-2 py-0.5 text-[10px] text-[#787B86] hover:text-[#D1D4DC] cursor-pointer"
                    >
                      {sub} <span className="text-[#4C525E]">☆</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Right: card grids */}
        <div className="flex-1 min-w-0 flex flex-col overflow-y-auto">
          {/* Section tabs */}
          <div className="flex items-center gap-0 border-b border-[#1E222D] px-3 bg-[#131722]">
            {SECTIONS.map((s) => (
              <button
                key={s.key}
                onClick={() => setSection(s.key)}
                className={`px-3 py-1.5 text-[11px] transition-colors ${
                  section === s.key
                    ? "bg-[#2962FF] text-white rounded"
                    : "text-[#787B86] hover:text-[#D1D4DC]"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Card grid */}
          <div className="flex-1 p-3">
            <div className="grid grid-cols-4 gap-3">
              {currentChains.map((chain: any, i: number) => {
                const pct = chain.change_pct ?? 0;
                return (
                  <div
                    key={chain.name ?? i}
                    className="bg-[#131722] border border-[#1E222D] rounded p-2 hover:border-[#2962FF]/40 cursor-pointer transition-colors"
                  >
                    <div className="text-[11px] text-[#D1D4DC] font-medium truncate mb-1">
                      {chain.name}
                    </div>
                    {chain.has_data && (
                      <div className={`text-[10px] tabular-nums ${signColor(pct)}`}>
                        {pct > 0 ? "+" : ""}{pct.toFixed(2)}%
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {data.timestamp && (
            <div className="text-[10px] text-[#4C525E] px-3 py-1 border-t border-[#1E222D]">
              {data.timestamp}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Fallback to markdown
  if (rawMd) {
    return <MarkdownRenderer markdown={rawMd} className="p-3" />;
  }

  return (
    <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
      加载中…
    </div>
  );
}
