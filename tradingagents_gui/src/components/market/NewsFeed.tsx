/**
 * NewsFeed — 24小时滚动市场资讯。
 */

import type { MarketNewsItem } from "../../lib/types";

interface Props {
  news: MarketNewsItem[];
}

export default function NewsFeed({ news }: Props) {
  if (news.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-[#4C525E] text-xs">
        暂无资讯
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="text-[12px] text-[#D1D4DC] font-medium px-2 py-1.5 border-b border-[#1E222D]">
        24小时滚动
        <span className="text-[10px] text-[#4C525E] font-normal ml-1">（{news.length} 条）</span>
      </div>
      <div className="divide-y divide-[#1E222D]/60">
        {news.map((item, i) => (
          <div key={i} className="px-2 py-1.5 hover:bg-[#2A2E39]/30">
            <div className="flex items-start gap-2">
              <span className="text-[10px] text-[#4C525E] whitespace-nowrap mt-0.5">{item.time}</span>
              <div className="flex-1 min-w-0">
                <div className="text-[11px] text-[#D1D4DC] leading-tight truncate">{item.title}</div>
                {item.content && item.content !== item.title && (
                  <div className="text-[10px] text-[#787B86] leading-tight mt-0.5 line-clamp-2">{item.content}</div>
                )}
              </div>
              <span className="text-[9px] text-[#4C525E] whitespace-nowrap">{item.source}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
