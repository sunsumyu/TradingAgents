/**
 * Ticket 03 — legacy shim delegation test.
 *
 * The 对拍 that justified unification was run BEFORE migration and its result is
 * recorded in `markdown-renderer.test.tsx` (headings / lists / emphasis were
 * lossy in the self-built renderer; pipe tables were equivalent).
 *
 * After migration `astock/MarkdownRenderer` is a `@deprecated` shim that
 * delegates to `shared/Markdown`. The invariant now is simple and total:
 * the shim must render byte-identical output to the unified renderer for every
 * sample — i.e. there is exactly ONE active implementation.
 */

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import LegacyShim from "../astock/MarkdownRenderer";
import UnifiedMarkdown from "../shared/Markdown";

const SAMPLES: Record<string, string> = {
  headers: "# 一级标题\n\n## 二级标题\n\n### 三级标题",
  pipe_table:
    "| 代码 | 名称 | 价格 |\n| --- | --- | --- |\n| 600519 | 贵州茅台 | 1700.00 |\n| 000001 | 平安银行 | 11.50 |",
  header_plus_table: "## 大宗交易明细\n\n| 代码 | 溢价率 |\n| --- | --- |\n| 600519 | -2.3% |",
  plain_text: "这是一段纯文本，没有任何 markdown 结构。",
  mixed: "# 报告\n\n正文一段。\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n结尾文字。",
  lists: "- 项目一\n- 项目二\n\n1. 第一\n2. 第二",
  emphasis: "**加粗** 与 *斜体* 与 `代码`",
  empty: "",
};

describe("legacy shim delegates to the unified renderer (ticket 03)", () => {
  for (const [name, md] of Object.entries(SAMPLES)) {
    it(`${name}: identical output`, () => {
      const viaShim = renderToStaticMarkup(
        <LegacyShim markdown={md} className="p-3" />,
      );
      const viaUnified = renderToStaticMarkup(
        <UnifiedMarkdown markdown={md} className="p-3" />,
      );
      expect(viaShim).toBe(viaUnified);
    });
  }

  it("shim preserves the className passthrough", () => {
    const html = renderToStaticMarkup(
      <LegacyShim markdown={"# 标题"} className="p-3" />,
    );
    expect(html).toContain("p-3");
  });
});
