/**
 * InvestmentCalendarPanel — 投资日历面板。
 *
 * Shows grouped events for a given date:
 * - IPO listing (首发新股上市)
 * - IPO declaration (首发新股发行)
 * - Suspension/resumption (沪深停复牌)
 * - Special treatment (特别处理)
 * - Lockup expiry (限售解禁)
 *
 * Each group has a count and expandable detail table.
 */

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { InvestmentCalendarData, CalendarEventGroup } from "../../lib/types";
import { formatDateDisplay } from "../../lib/dateFormat";
import { useLanguage } from "../../lib/useLanguage";
import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: InvestmentCalendarData;
  rawMd: string;
  onStockClick?: (ticker: string) => void;
}

type GroupKey = keyof InvestmentCalendarData;

interface GroupConfig {
  key: GroupKey;
  label: string;
  color: string;
  columns: string[];
}

const GROUPS: GroupConfig[] = [
  { key: "ipo_listing", label: "首发新股上市", color: "#2962FF", columns: ["代码", "简称", "说明"] },
  { key: "ipo_declaration", label: "首发新股发行", color: "#26A69A", columns: ["代码", "简称", "说明"] },
  { key: "suspension_resumption", label: "沪深停复牌", color: "#FF9800", columns: ["代码", "简称", "停牌时间", "复牌时间", "说明", "原因"] },
  { key: "special_treatment", label: "特别处理", color: "#E040FB", columns: ["代码", "简称", "说明"] },
  { key: "lockup_expiry", label: "限售解禁", color: "#EF5350", columns: ["代码", "简称", "解禁日期", "解禁数量(万)", "占总股本%", "解禁原因"] },
];

function CalendarEventRow({ event, columns, onStockClick }: { event: CalendarEventGroup; columns: string[]; onStockClick?: (ticker: string) => void }) {
  const cells: Record<string, string | number | undefined> = {
    code: event.code,
    name: event.name,
    description: event.description,
    suspend_date: event.suspend_date,
    resume_date: event.resume_date,
    reason: event.reason,
    date: event.date,
    quantity_wan: event.quantity_wan,
    ratio_pct: event.ratio_pct,
  };

  const cellMap: Record<string, keyof typeof cells> = {
    代码: "code",
    简称: "name",
    说明: "description",
    停牌时间: "suspend_date",
    复牌时间: "resume_date",
    原因: "reason",
    解禁日期: "date",
    "解禁数量(万)": "quantity_wan",
    "占总股本%": "ratio_pct",
  };

  return (
    <tr className="border-b border-[#1E222D]/60 last:border-0 hover:bg-[#2A2E39]/50">
      {columns.map((col) => {
        const key = cellMap[col];
        const val = key ? cells[key] : undefined;
        const isCode = col === "代码";
        return (
          <td
            key={col}
            className={`px-2.5 py-1.5 text-[11px] ${
              isCode ? "text-left" : "text-right"
            } tabular-nums text-[#D1D4DC]`}
          >
            {isCode && val ? (
              onStockClick ? (
                <button
                  className="text-[#2962FF] hover:underline cursor-pointer bg-transparent border-0 p-0 font-mono"
                  onClick={() => onStockClick(String(val))}
                >
                  {val}
                </button>
              ) : (
                <span className="text-[#2962FF] font-mono">{val}</span>
              )
            ) : (
              val ?? "—"
            )}
          </td>
        );
      })}
    </tr>
  );
}

function EventGroupSection({
  config,
  events,
  defaultOpen,
  onStockClick,
}: {
  config: GroupConfig;
  events: CalendarEventGroup[];
  defaultOpen: boolean;
  onStockClick?: (ticker: string) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!events || events.length === 0) return null;

  return (
    <div className="mb-3">
      <button
        className="w-full flex items-center gap-2 text-left cursor-pointer bg-transparent border-0 p-0"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown size={14} className="text-[#787B86]" /> : <ChevronRight size={14} className="text-[#787B86]" />}
        <span className="w-1 h-3.5 rounded-full" style={{ backgroundColor: config.color }} />
        <span className="text-[12px] text-[#D1D4DC] font-medium">{config.label}</span>
        <span className="text-[10px] text-[#787B86] font-normal">（共 {events.length} 条记录）</span>
      </button>
      {open && (
        <div className="mt-1 overflow-x-auto rounded border border-[#1E222D]">
          <table className="w-full text-[11px] border-collapse">
            <thead>
              <tr className="bg-[#1E222D]/80 border-b border-[#2A2E39]">
                {config.columns.map((col) => (
                  <th key={col} className={`px-2.5 py-1.5 text-[#787B86] font-medium ${col === "代码" ? "text-left" : "text-right"}`}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {events.map((event, i) => (
                <CalendarEventRow key={`${event.code}-${i}`} event={event} columns={config.columns} onStockClick={onStockClick} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function InvestmentCalendarPanel({ data, rawMd, onStockClick }: Props) {
  const lang = useLanguage();
  const hasAnyEvent = GROUPS.some((g) => {
    const events = data?.[g.key];
    return Array.isArray(events) && events.length > 0;
  });

  if (!hasAnyEvent) {
    return (
      <div className="h-full overflow-y-auto">
        {rawMd ? (
          <MarkdownRenderer markdown={rawMd} className="p-3" />
        ) : (
          <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
            当日无特别市场事件
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3">
      {data?.date && (
        <div className="text-[11px] text-[#787B86] mb-3">
          投资日历 | {formatDateDisplay(data.date, lang)}
        </div>
      )}
      {GROUPS.map((config) => {
        const events = data?.[config.key];
        if (!Array.isArray(events) || events.length === 0) return null;
        return (
          <EventGroupSection
            key={config.key}
            config={config}
            events={events}
            defaultOpen={true}
            onStockClick={onStockClick}
          />
        );
      })}
    </div>
  );
}
