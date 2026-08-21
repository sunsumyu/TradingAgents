import { useState } from "react";
import { ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import type { NewsItem } from "../../lib/types";

interface Props {
  items: NewsItem[];
}

export default function NewsFeed({ items }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (items.length === 0) {
    return (
      <div className="text-[12px] text-[#787B86] py-4 text-center">
        暂无相关新闻
      </div>
    );
  }

  return (
    <div className="space-y-1 max-h-[300px] overflow-y-auto">
      {items.map((item, i) => (
        <div
          key={i}
          className="group px-3 py-2 rounded hover:bg-[#2A2E39] transition-colors cursor-pointer"
          onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
        >
          <div className="flex items-start gap-2">
            <div className="flex-1 min-w-0">
              <div className="text-[13px] text-[#D1D4DC] leading-tight truncate">
                {item.title}
              </div>
              <div className="flex items-center gap-2 mt-1">
                {item.publisher && (
                  <span className="text-[11px] text-[#787B86]">{item.publisher}</span>
                )}
                {item.pub_date && (
                  <span className="text-[11px] text-[#555]">{item.pub_date}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {item.link && (
                <a
                  href={item.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink size={12} className="text-[#787B86]" />
                </a>
              )}
              {item.summary && (
                expandedIdx === i ? <ChevronUp size={12} className="text-[#787B86]" /> : <ChevronDown size={12} className="text-[#787B86]" />
              )}
            </div>
          </div>
          {expandedIdx === i && item.summary && (
            <div className="mt-2 text-[12px] text-[#787B86] leading-relaxed pl-0">
              {item.summary}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
