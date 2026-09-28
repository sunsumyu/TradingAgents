/**
 * DataSourceNotice — explicit data-source warning banner (tickets 08/09).
 *
 * Four market-page tabs are served by features with NO verified data source
 * (or a verified-wrong one). The backend keeps returning honest static text,
 * but a full markdown block under a normal-looking tab still reads as "data".
 * This banner makes the state impossible to miss.
 *
 *   - "mislabel":    the source returns DIFFERENT market's data (hk_ipo → A股)
 *   - "unavailable": no public API source wired yet (us_ipo / neeq / st_changes)
 *   - "partial":     source works but covers less than the tab implies
 *
 * Evidence: 2026-09-27 probe — see .scratch/eastmoney-align/issues/08, 09.
 */

export type NoticeKind = "mislabel" | "unavailable" | "partial";

const STYLES: Record<NoticeKind, { bg: string; border: string; text: string; icon: string; label: string }> = {
  mislabel: {
    bg: "bg-[#F23645]/10",
    border: "border-[#F23645]/40",
    text: "text-[#F23645]",
    icon: "✕",
    label: "数据源有误",
  },
  unavailable: {
    bg: "bg-[#FF9800]/10",
    border: "border-[#FF9800]/40",
    text: "text-[#FF9800]",
    icon: "⚠",
    label: "数据源未接入",
  },
  partial: {
    bg: "bg-[#2962FF]/10",
    border: "border-[#2962FF]/40",
    text: "text-[#787B86]",
    icon: "ℹ",
    label: "数据源不完整",
  },
};

export default function DataSourceNotice({ kind, children }: { kind: NoticeKind; children: string }) {
  const s = STYLES[kind];
  return (
    <div className={`mx-3 mt-3 mb-1 px-3 py-2 rounded border ${s.bg} ${s.border} flex items-start gap-2`}>
      <span className={`${s.text} text-[12px] font-semibold leading-5 shrink-0`}>
        {s.icon} {s.label}
      </span>
      <span className="text-[11px] text-[#787B86] leading-5">{children}</span>
    </div>
  );
}
