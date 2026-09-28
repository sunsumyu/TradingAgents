/**
 * Ticket 03 — unified renderer capability test.
 *
 * BEFORE migration the platform had two renderers. Probing them on the same
 * samples produced these recorded gaps (legacy = self-built `MarkdownRenderer`):
 *
 *   construct        legacy                          react-markdown+remark-gfm
 *   headings         styled <div>, no <hN> anchor    semantic <h1>…<h4>
 *   pipe tables      OK (th/td/row widths equal)     OK (identical)
 *   lists            plain text, no <ul>/<li>        <ul>/<ol>/<li>
 *   inline emphasis  emitted verbatim (**加粗**)      <strong>/<em>
 *
 * Tables were equivalent (that is why the 对拍 passed for them); headings,
 * lists and emphasis were lossy. The platform therefore unified on
 * `shared/Markdown` (react-markdown). Legacy is now a `@deprecated` shim that
 * delegates to it, so this file asserts the ONE renderer's capabilities.
 */

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import Markdown from "../shared/Markdown";

const SAMPLES = {
  headers: "# 一级标题\n\n## 二级标题\n\n### 三级标题",
  pipe_table:
    "| 代码 | 名称 | 价格 |\n| --- | --- | --- |\n| 600519 | 贵州茅台 | 1700.00 |\n| 000001 | 平安银行 | 11.50 |",
  header_plus_table: "## 大宗交易明细\n\n| 代码 | 溢价率 |\n| --- | --- |\n| 600519 | -2.3% |",
  lists: "- 项目一\n- 项目二\n\n1. 第一\n2. 第二",
  emphasis: "**加粗** 与 *斜体* 与 `代码`",
  plain_text: "这是一段纯文本，没有任何 markdown 结构。",
  mixed: "# 报告\n\n正文一段。\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n- 结尾一项",
};

function render(md: string): string {
  return renderToStaticMarkup(<Markdown markdown={md} />);
}

function stripTags(s: string): string {
  return s.replace(/<[^>]+>/g, "").trim();
}

describe("unified Markdown renderer (ticket 03)", () => {
  it("returns null for empty input", () => {
    expect(renderToStaticMarkup(<Markdown markdown="" />)).toBe("");
  });

  it("applies the compact theme wrapper", () => {
    expect(render("hello")).toContain("prose-compact");
  });

  it("emits semantic headings (required for TOC anchors)", () => {
    const html = render(SAMPLES.headers);
    const headings = [...html.matchAll(/<h([1-6])[^>]*>(.*?)<\/h\1>/gis)].map((m) => ({
      level: Number(m[1]),
      text: stripTags(m[2]),
    }));
    expect(headings).toEqual([
      { level: 1, text: "一级标题" },
      { level: 2, text: "二级标题" },
      { level: 3, text: "三级标题" },
    ]);
  });

  it("renders pipe tables with the right cell counts", () => {
    const html = render(SAMPLES.pipe_table);
    expect([...html.matchAll(/<th[^>]*>(.*?)<\/th>/gis)].map((m) => stripTags(m[1]))).toEqual([
      "代码",
      "名称",
      "价格",
    ]);
    const tds = [...html.matchAll(/<td[^>]*>(.*?)<\/td>/gis)].map((m) => stripTags(m[1]));
    expect(tds).toEqual(["600519", "贵州茅台", "1700.00", "000001", "平安银行", "11.50"]);
  });

  it("wraps tables in a horizontal scroll container", () => {
    const html = render(SAMPLES.pipe_table);
    expect(html).toContain("overflow-x-auto");
  });

  it("renders lists (legacy could not)", () => {
    const html = render(SAMPLES.lists);
    expect([...html.matchAll(/<li[^>]*>(.*?)<\/li>/gis)].map((m) => stripTags(m[1]))).toEqual([
      "项目一",
      "项目二",
      "第一",
      "第二",
    ]);
    expect(html).toContain("<ul>");
    expect(html).toContain("<ol>");
  });

  it("renders inline emphasis (legacy emitted it verbatim)", () => {
    const html = render(SAMPLES.emphasis);
    expect(html).toContain("<strong>加粗</strong>");
    expect(html).toContain("<em>斜体</em>");
    expect(html).toContain("<code>代码</code>");
  });

  it("renders a mixed document without dropping sections", () => {
    const html = render(SAMPLES.mixed);
    expect(html).toMatch(/<h1[^>]*>报告<\/h1>/);
    expect(html).toContain("正文一段。");
    expect(html).toContain("<table>");
    expect(html).toContain("结尾一项");
  });

  it("passes plain text through", () => {
    expect(render(SAMPLES.plain_text)).toContain("这是一段纯文本");
  });
});
