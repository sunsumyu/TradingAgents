/**
 * ResearchReportsPanel — 研报流面板（Phase 12.05）。
 *
 * 数据来自东财 reportapi 研究报告（`research_reports`）。
 * 标题长 → 列表渲染：日期 + 评级徽标（涨跌色）+ 券商·分析师 + 标题。
 * 评级为券商观点，非本平台结论。
 */

import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data?: Record<string, unknown>;
  rawMd: string;
  loading?: boolean;
}

interface ReportItem {
  publish_date?: string;
  org_name?: string;
  rating?: string;
  researcher?: string;
  title?: string;
}

const RATING_UP = new Set(["买入", "增持", "推荐", "强推", "优于大市"]);
const RATING_DOWN = new Set(["减持", "卖出", "中性偏空"]);

function ratingClass(rating?: string): string {
  if (rating && RATING_UP.has(rating)) return "text-up";
  if (rating && RATING_DOWN.has(rating)) return "text-down";
  return "text-text-secondary";
}

export default function ResearchReportsPanel({ data, rawMd, loading = false }: Props) {
  const items = (Array.isArray((data as { items?: unknown })?.items)
    ? ((data as { items: ReportItem[] }).items)
    : []) as ReportItem[];

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="text-[12px] text-text-primary font-medium px-3 pt-3 flex items-center gap-2">
        <span className="w-1 h-3.5 rounded-full bg-[#AB47BC]" />
        研报流
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto px-3 pb-3">
        {items.length > 0 ? (
          <ul className="divide-y divide-line/50">
            {items.map((it, i) => (
              <li key={i} className="py-1.5 flex items-start gap-2 text-[11px]">
                <span className="text-text-muted tabular-nums shrink-0 pt-px">
                  {it.publish_date ?? "—"}
                </span>
                <span
                  className={`shrink-0 px-1.5 py-px rounded bg-bg-hover font-medium ${ratingClass(it.rating)}`}
                >
                  {it.rating ?? "—"}
                </span>
                <span className="text-text-secondary shrink-0">
                  {(it.org_name ?? "—") + (it.researcher ? `·${it.researcher}` : "")}
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
            {loading ? "加载中…" : "暂无研报数据"}
          </div>
        )}
      </div>
    </div>
  );
}
