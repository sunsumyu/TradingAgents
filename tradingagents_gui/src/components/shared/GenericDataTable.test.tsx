/**
 * Ticket 05 — GenericDataTable unit tests.
 *
 * Covers the acceptance criteria: column-definition-driven cell rendering
 * (format/unit), sorting, pagination, loading / empty states, and the
 * `kind: "raw"` degradation path.
 */

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import GenericDataTable, { rowsFromData } from "./GenericDataTable";
import type { FeatureColumn } from "../../lib/types";

const COLS: FeatureColumn[] = [
  { key: "code", label: "代码", unit: "text", format: "text" },
  { key: "name", label: "名称", unit: "text", format: "text" },
  { key: "premium_pct", label: "溢价率", unit: "percent", format: "float2" },
  { key: "net_buy", label: "净买入", unit: "万元", format: "signed" },
  { key: "amount_wan", label: "成交额", unit: "万元", format: "float2" },
];

const ROWS = [
  { code: "600519", name: "贵州茅台", premium_pct: -2.3, net_buy: -1500, amount_wan: 15000.5 },
  { code: "000001", name: "平安银行", premium_pct: 1.5, net_buy: 320, amount_wan: 800.25 },
  { code: "300750", name: "宁德时代", premium_pct: null, net_buy: 0, amount_wan: 4200 },
];

function render(props: Partial<React.ComponentProps<typeof GenericDataTable>> = {}) {
  return renderToStaticMarkup(
    <GenericDataTable columns={COLS} rows={ROWS} {...props} />,
  );
}

describe("GenericDataTable", () => {
  it("renders one header cell per column definition", () => {
    const html = render();
    for (const col of COLS) expect(html).toContain(col.label);
  });

  it("formats percent cells with the % suffix", () => {
    const html = render();
    expect(html).toContain("-2.30%");
    expect(html).toContain("1.50%");
  });

  it("formats numeric cells to the declared precision", () => {
    const html = render();
    expect(html).toContain("15000.50");
    expect(html).toContain("800.25");
    expect(html).toContain("4200.00");
  });

  it("prefixes + only for positive signed values", () => {
    const html = render();
    expect(html).toContain("+320");
    expect(html).toContain("-1500");
    // a zero signed value gets no sign (formatFeatureCell contract)
    expect(html).not.toContain("+0");
  });

  it("renders a dash for null values instead of 'null'", () => {
    const html = render();
    expect(html).toContain("—");
    expect(html).not.toContain("null");
  });

  it("colors positive/negative signed and percent cells", () => {
    const html = render();
    expect(html).toContain("text-down"); // -2.30% / -1500
    expect(html).toContain("text-up"); // 1.50% / +320
  });

  it("shows the empty state when there are no rows", () => {
    const html = render({ rows: [], emptyText: "没有大宗交易" });
    expect(html).toContain("没有大宗交易");
    expect(html).not.toContain("<table");
  });

  it("shows the loading state on first load", () => {
    const html = render({ rows: [], loading: true });
    expect(html).toContain("加载中");
  });

  it("degrades to markdown with a 未结构化 badge when kind=raw", () => {
    const html = render({
      kind: "raw",
      rawMd: "# 大宗交易\n\n| A | B |\n| --- | --- |\n| 1 | 2 |",
    });
    expect(html).toContain("未结构化");
    expect(html).toContain("<table");
    expect(html).not.toContain("成交额"); // no structured columns rendered
  });

  it("degrades when columns are missing but raw markdown exists", () => {
    const html = renderToStaticMarkup(
      <GenericDataTable columns={[]} rows={ROWS} rawMd="原始内容" />,
    );
    expect(html).toContain("未结构化");
    expect(html).toContain("原始内容");
  });

  it("renders provenance when provided", () => {
    const html = render({ provenance: { source: "eastmoney", as_of: "2026-09-27" } });
    expect(html).toContain("eastmoney");
    expect(html).toContain("2026-09-27");
  });

  it("paginates and shows a page indicator above the page size", () => {
    const many = Array.from({ length: 120 }, (_, i) => ({
      code: String(i).padStart(6, "0"),
      name: `股票${i}`,
      premium_pct: i / 10,
      amount_wan: i,
    }));
    const html = render({ rows: many, pageSize: 50 });
    expect(html).toContain("1 / 3 页");
    expect(html).toContain("共 120 条");
    // only the first page's rows are present
    expect(html).toContain("股票0");
    expect(html).not.toContain("股票60");
  });

  it("does not paginate when rows fit in one page", () => {
    expect(render()).not.toContain("页");
  });

  it("makes headers clickable for sorting", () => {
    const html = render();
    expect(html).toContain("cursor-pointer");
  });

  it("right-aligns numeric columns, left-aligns text columns", () => {
    const html = render();
    expect(html).toContain("text-right");
    expect(html).toContain("text-left");
  });
});

describe("rowsFromData adapter", () => {
  it("extracts the items array from a backend parser result", () => {
    expect(rowsFromData({ items: [{ a: 1 }], total: 1 })).toEqual([{ a: 1 }]);
  });

  it("returns null when there is no items array", () => {
    expect(rowsFromData({})).toBeNull();
    expect(rowsFromData(null)).toBeNull();
    expect(rowsFromData(undefined)).toBeNull();
  });
});
