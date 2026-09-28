/**
 * StockNoticesPanel — 公司公告面板（Phase 12.04）。
 *
 * 数据来自东财 np-anotice 个股公告流（`stock_notices`）。
 * 标题较长，用列表而非表格渲染：日期 + 分类徽标 + 标题。
 */

import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: Record<string, unknown>;
  rawMd: string;
  loading?: boolean;
}

interface NoticeItem {
  notice_date?: string;
  column_name?: string;
  title?: string;
}

export default function StockNoticesPanel({ data, rawMd, loading = false }: Props) {
  const items = (Array.isArray((data as { items?: unknown })?.items)
    ? ((data as { items: NoticeItem[] }).items)
    : []) as NoticeItem[];

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="text-[12px] text-text-primary font-medium px-3 pt-3 flex items-center gap-2">
        <span className="w-1 h-3.5 rounded-full bg-[#F57C00]" />
        公司公告
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto px-3 pb-3">
        {items.length > 0 ? (
          <ul className="divide-y divide-line/50">
            {items.map((it, i) => (
              <li key={i} className="py-1.5 flex items-start gap-2 text-[11px]">
                <span className="text-text-muted tabular-nums shrink-0 pt-px">
                  {it.notice_date ?? "—"}
                </span>
                <span className="shrink-0 px-1.5 py-px rounded bg-bg-hover text-text-secondary">
                  {it.column_name ?? "公告"}
                </span>
                <span className="text-text-primary leading-4">{it.title ?? ""}</span>
              </li>
            ))}
          </ul>
        ) : rawMd ? (
          <div className="pt-2 text-text-secondary">
            <MarkdownRenderer markdown={rawMd} />
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-text-muted text-xs">
            {loading ? "加载中…" : "暂无公告数据"}
          </div>
        )}
      </div>
    </div>
  );
}
