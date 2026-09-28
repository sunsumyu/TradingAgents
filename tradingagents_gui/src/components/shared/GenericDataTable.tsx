/**
 * GenericDataTable — column-definition-driven table for structured feature data
 * (ticket 05).
 *
 * Consumes the unified payload contract (ticket 02):
 *   { kind, columns, rows, provenance }  — or a `{ items: [...] }` container.
 *
 * Responsibilities:
 *   - render cells through `formatFeatureCell` (unit + format hints from the
 *     column definition — the renderer never infers)
 *   - client-side sort (click a header) and pagination (default 50/page)
 *   - loading / empty states
 *   - `kind: "raw"` degradation: render markdown with an explicit "未结构化" badge
 *
 * Panels should declare columns and hand over rows — no per-panel table code.
 */

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Info } from "lucide-react";
import type {
  FeatureColumn,
  FeaturePayloadEnvelope,
  FeatureProvenance,
} from "../../lib/types";
import { formatFeatureCell } from "../../lib/types";
import Markdown from "./Markdown";

const DEFAULT_PAGE_SIZE = 50;

export type SortDir = "asc" | "desc";

/** Columns whose sign carries meaning get up/down colouring. */
function isSignedCol(c: FeatureColumn): boolean {
  return c.format === "signed" || c.unit === "percent";
}

interface GenericDataTableProps {
  columns: FeatureColumn[];
  rows: Record<string, unknown>[];
  provenance?: FeatureProvenance;
  /** `"raw"`: no structured columns — render `rawMd` with a degradation badge. */
  kind?: "table" | "raw";
  rawMd?: string;
  loading?: boolean;
  emptyText?: string;
  pageSize?: number;
  className?: string;
}

function isNumeric(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function compare(a: unknown, b: unknown): number {
  if (isNumeric(a) && isNumeric(b)) return a - b;
  if (a == null) return b == null ? 0 : -1;
  if (b == null) return 1;
  return String(a).localeCompare(String(b), "zh-Hans-CN");
}

function RawFallback({ rawMd, className }: { rawMd: string; className: string }) {
  return (
    <div className={className}>
      <div className="flex items-center gap-1.5 px-2 py-1.5 mb-2 rounded bg-bg-hover/60 text-[10px] text-text-muted">
        <Info size={11} />
        未结构化 — 此后端数据尚无列定义，按原始格式渲染
      </div>
      <Markdown markdown={rawMd} />
    </div>
  );
}

export default function GenericDataTable({
  columns,
  rows,
  provenance,
  kind = "table",
  rawMd = "",
  loading = false,
  emptyText = "暂无数据",
  pageSize = DEFAULT_PAGE_SIZE,
  className = "h-full overflow-y-auto p-3",
}: GenericDataTableProps) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const c = compare(a[sortKey], b[sortKey]);
      return sortDir === "asc" ? c : -c;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = useMemo(
    () => sorted.slice(safePage * pageSize, safePage * pageSize + pageSize),
    [sorted, safePage, pageSize],
  );

  // ── Degradation / empty / loading ────────────────────────────────────────
  // No structured columns, or the backend explicitly said `kind: "raw"`:
  // fall back to markdown with a visible "not structured" badge.
  if (kind === "raw" || columns.length === 0) {
    if (rawMd) return <RawFallback rawMd={rawMd} className={className} />;
    return (
      <div className={`flex items-center justify-center h-full text-text-muted text-xs ${className}`}>
        {loading ? "加载中…" : emptyText}
      </div>
    );
  }

  if (loading && rows.length === 0) {
    return (
      <div className={`flex items-center justify-center h-full text-text-muted text-xs ${className}`}>
        加载中…
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className={`flex items-center justify-center h-full text-text-muted text-xs ${className}`}>
        {emptyText}
      </div>
    );
  }

  const toggleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
    setPage(0);
  };

  // Right-align numeric columns (units that are not text/date).
  const isNumCol = (c: FeatureColumn) =>
    c.unit !== "text" && c.unit !== "date" && c.format !== "text" && c.format !== "date";

  return (
    <div className={className}>
      {provenance?.source && (
        <div className="text-[10px] text-text-muted mb-1.5">
          数据源：{provenance.source}
          {provenance.as_of ? ` · ${provenance.as_of}` : ""}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px]">
          <thead>
            <tr className="border-b border-line">
              {columns.map((col) => {
                const active = sortKey === col.key;
                return (
                  <th
                    key={col.key}
                    onClick={() => toggleSort(col.key)}
                    className={`px-2 py-1.5 font-medium text-text-secondary whitespace-nowrap cursor-pointer select-none hover:text-text-primary ${
                      isNumCol(col) ? "text-right" : "text-left"
                    }`}
                    title={`按 ${col.label} 排序`}
                  >
                    <span className="inline-flex items-center gap-0.5">
                      {col.label}
                      {active &&
                        (sortDir === "asc" ? <ArrowUp size={10} /> : <ArrowDown size={10} />)}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, i) => (
              <tr
                key={i}
                className="border-b border-line/50 hover:bg-bg-hover/50 transition-colors"
              >
                {columns.map((col) => {
                  const value = row[col.key];
                  const text = formatFeatureCell(value, col);
                  const colored = isSignedCol(col) && isNumeric(value) && value !== 0;
                  const cls = colored
                    ? value > 0
                      ? "text-up"
                      : "text-down"
                    : isNumCol(col)
                      ? "text-text-secondary tabular-nums"
                      : "text-text-primary";
                  return (
                    <td
                      key={col.key}
                      className={`px-2 py-1 whitespace-nowrap ${
                        isNumCol(col) ? "text-right" : "text-left"
                      } ${cls}`}
                    >
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-end gap-2 mt-2 text-[10px] text-text-muted">
          <span>
            {safePage + 1} / {pageCount} 页 · 共 {sorted.length} 条
          </span>
          <button
            className="p-0.5 hover:bg-bg-hover rounded disabled:opacity-30"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={safePage === 0}
            aria-label="上一页"
          >
            <ChevronLeft size={12} />
          </button>
          <button
            className="p-0.5 hover:bg-bg-hover rounded disabled:opacity-30"
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={safePage >= pageCount - 1}
            aria-label="下一页"
          >
            <ChevronRight size={12} />
          </button>
        </div>
      )}
    </div>
  );
}

// ── Adapter for the current backend envelope ──────────────────────────────────
//
// Backend parsers return `data = { items: [...], total: N }` and the envelope
// carries `raw_md`. Panels pass that plus their column definitions; this helper
// normalises both the new `{columns, rows}` payload and the `{items}` container.

export interface FeatureTableDataProps {
  columns: FeatureColumn[];
  data?: Record<string, unknown> | null;
  payload?: FeaturePayloadEnvelope | null;
  rawMd?: string;
  loading?: boolean;
  emptyText?: string;
  className?: string;
}

export function rowsFromData(
  data?: Record<string, unknown> | null,
): Record<string, unknown>[] | null {
  if (!data) return null;
  const items = (data as { items?: unknown }).items;
  if (Array.isArray(items)) return items as Record<string, unknown>[];
  return null;
}

export function FeatureDataTable({
  columns,
  data,
  payload,
  rawMd = "",
  loading = false,
  emptyText,
  className,
}: FeatureTableDataProps) {
  const rows = payload?.rows ?? rowsFromData(data) ?? [];
  const kind = payload?.kind ?? "table";
  return (
    <GenericDataTable
      columns={columns}
      rows={rows}
      kind={kind}
      rawMd={payload?.raw_md || rawMd}
      provenance={payload?.provenance}
      loading={loading}
      emptyText={emptyText}
      className={className}
    />
  );
}
