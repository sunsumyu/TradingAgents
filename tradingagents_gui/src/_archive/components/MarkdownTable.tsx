/**
 * MarkdownTable — Parse and render markdown tables as structured HTML tables.
 *
 * Handles pipes (|) separated tables, aligns columns, and applies
 * TradingAgents theme colors.
 */

interface Props {
  markdown: string;
  className?: string;
}

// Parse a markdown table row into cells
function parseRow(line: string): string[] {
  return line
    .split("|")
    .map((cell) => cell.trim())
    .filter((cell) => cell.length > 0);
}

// Check if a line is a separator (e.g., "---|---|---")
function isSeparator(line: string): boolean {
  return /^\|?[\s\-:|]+\|?$/.test(line);
}

export default function MarkdownTable({ markdown, className = "" }: Props) {
  const lines = markdown.split("\n").filter((line) => line.trim().length > 0);

  // Find table blocks (lines containing |)
  const tables: string[][][] = [];
  let currentTable: string[] = [];

  for (const line of lines) {
    if (line.includes("|")) {
      currentTable.push(line);
    } else {
      if (currentTable.length > 0) {
        tables.push(currentTable.map(parseRow));
        currentTable = [];
      }
    }
  }
  if (currentTable.length > 0) {
    tables.push(currentTable.map(parseRow));
  }

  // If no tables found, render as plain text with sections
  if (tables.length === 0) {
    return (
      <div className={`text-[12px] text-text-secondary whitespace-pre-wrap leading-relaxed font-mono ${className}`}>
        {markdown}
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {tables.map((table, tableIdx) => {
        // Filter out separator rows
        const dataRows = table.filter((row) => !isSeparator(row.join(" | ")));
        if (dataRows.length === 0) return null;

        // First row is header
        const header = dataRows[0];
        const body = dataRows.slice(1);

        return (
          <div key={tableIdx} className="bg-bg-secondary rounded-lg border border-line overflow-hidden">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-line">
                  {header.map((cell, i) => (
                    <th
                      key={i}
                      className="text-left px-3 py-2 text-text-secondary font-medium"
                    >
                      {cell}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {body.map((row, rowIdx) => (
                  <tr
                    key={rowIdx}
                    className="border-b border-line/50 last:border-0 hover:bg-bg-hover/50 transition-colors"
                  >
                    {row.map((cell, cellIdx) => {
                      // Detect if cell contains percentage or number
                      const isPct = /[-+]?\d+\.?\d*%/.test(cell);
                      const isNum = /^[-+]?\d[\d,.]*$/.test(cell);
                      const isNegative = cell.includes("-") && isNum;

                      let cellClass = "text-text-primary";
                      if (isPct || (isNum && isNegative)) {
                        cellClass = cell.startsWith("-") ? "text-up" : "text-down";
                      } else if (isNum) {
                        cellClass = "text-text-secondary tabular-nums";
                      }

                      return (
                        <td key={cellIdx} className={`px-3 py-2 ${cellClass}`}>
                          {cell}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
