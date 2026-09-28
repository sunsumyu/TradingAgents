/**
 * EarningsForecastPanel — 财报数据面板（业绩预告 + 业绩快报 Tab）。
 */

import { useState } from "react";
import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: Record<string, unknown>;
  rawMd: string;
  feature?: string;
}

const TABS = [
  { key: "earnings_forecast", label: "业绩预告" },
  { key: "earnings_express", label: "业绩快报" },
];

export default function EarningsForecastPanel({ rawMd }: Props) {
  const [activeTab, setActiveTab] = useState("earnings_forecast");

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-0 border-b border-[#1E222D] px-2">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-3 py-1.5 text-[11px] ${
              activeTab === tab.key
                ? "text-[#2962FF] border-b-2 border-[#2962FF] font-medium"
                : "text-[#787B86] hover:text-[#D1D4DC]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {rawMd ? <MarkdownRenderer markdown={rawMd} /> : <div className="text-[#787B86] text-xs">加载中…</div>}
      </div>
    </div>
  );
}
