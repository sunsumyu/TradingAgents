/**
 * Shared DataTable component for all tabular data display.
 *
 * Used by: FinancialStatementPanel, NorthboundPanel, HotStockPanel,
 * InsiderTransactionsPanel, DragonTigerPanel, etc.
 */

export interface DataTableColumn {
  key: string;
  title: string;
  align?: "left" | "right" | "center";
  render?: (value: any, row: any, index: number) => React.ReactNode;
}

interface DataTableProps {
  columns: DataTableColumn[];
  data: any[];
  rowKey?: string | ((row: any) => string);
  className?: string;
  emptyText?: string;
  size?: "small" | "medium";
}

function getRowKey(row: any, rowKey: DataTableProps["rowKey"], index: number): string {
  if (typeof rowKey === "function") return rowKey(row);
  if (typeof rowKey === "string") return String(row[rowKey]);
  return String(index);
}

export default function DataTable({
  columns,
  data,
  rowKey,
  className = "",
  emptyText = "暂无数据",
  size = "small",
}: DataTableProps) {
  const sizeClasses = size === "small" 
    ? "text-[11px] [&_th]:px-2 [&_th]:py-1.5 [&_td]:px-2 [&_td]:py-1"
    : "text-xs [&_th]:px-3 [&_th]:py-2 [&_td]:px-3 [&_td]:py-1.5";

  if (data.length === 0) {
    return (
      <div className={`flex items-center justify-center h-20 text-text-secondary ${className}`}>
        {emptyText}
      </div>
    );
  }

  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className={`w-full border-collapse ${sizeClasses}`}>
        <thead>
          <tr className="border-b border-line bg-bg-secondary sticky top-0 z-10">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`font-medium text-text-secondary whitespace-nowrap ${
                  col.align === "right" ? "text-right" : 
                  col.align === "center" ? "text-center" : "text-left"
                }`}
              >
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr 
              key={getRowKey(row, rowKey, idx)}
              className="border-b border-line/50 hover:bg-bg-hover/50 transition-colors"
            >
              {columns.map((col) => (
                <td 
                  key={col.key}
                  className={`whitespace-nowrap ${
                    col.align === "right" ? "text-right tabular-nums" : 
                    col.align === "center" ? "text-center" : "text-left"
                  }`}
                >
                  {col.render ? col.render(row[col.key], row, idx) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Format number with sign (+/-) and color class */
export function formatSigned(value: number | null | undefined): { text: string; className: string } {
  if (value == null) return { text: "—", className: "text-text-secondary" };
  const sign = value > 0 ? "+" : "";
  const cls = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-text-secondary";
  return { text: `${sign}${value.toFixed(2)}`, className: cls };
}

/** Format large numbers with 万/亿 suffix */
export function formatWanYi(value: number): string {
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(2)}万`;
  return value.toFixed(2);
}

/** Parse markdown table text into {columns, data} */
export function parseMarkdownTable(markdown: string): { columns: DataTableColumn[]; data: any[] } {
  const lines = markdown.split("\n").filter((l) => l.trim());
  if (lines.length < 2) return { columns: [], data: [] };

  // Find header row (first line with |)
  let headerIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes("|")) { headerIdx = i; break; }
  }
  if (headerIdx === -1) return { columns: [], data: [] };

  const parseRow = (line: string): string[] =>
    line.split("|").map((c) => c.trim()).filter((c) => c.length > 0);

  const headers = parseRow(lines[headerIdx]);
  const columns: DataTableColumn[] = headers.map((h, i) => ({
    key: `col_${i}`,
    title: h,
    align: i > 0 ? "right" : "left",
  }));

  const data = lines
    .slice(headerIdx + 1)
    .filter((l) => l.includes("|") && !/^[\s|\-:]+$/.test(l))
    .map((line) => {
      const cells = parseRow(line);
      const row: any = {};
      columns.forEach((col, i) => {
        row[col.key] = cells[i] ?? "";
      });
      return row;
    });

  return { columns, data };
}
