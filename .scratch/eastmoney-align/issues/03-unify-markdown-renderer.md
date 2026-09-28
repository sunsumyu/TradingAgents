# 03 — markdown 渲染器统一

**What to build:** 平台当前并存两套 markdown 渲染（报告页的 `react-markdown`、A股特色面板的自研 `MarkdownRenderer`）。统一为单一活跃渲染器：先对同一输入做两侧输出对拍，确认等价后逐处切换；自研渲染器**保留并标注 `@deprecated`**（不删除），全部调用点迁移后再由用户决定是否清理。同时移除遗留的调试日志。

**Blocked by:** None — can start immediately.

**Status:** done (2026-09-27)

- [x] 用代表性 markdown 样本（标题、管道表、列表、嵌套）对拍两套渲染器输出，记录差异
- [x] 修复差异后，按调用点分批切到统一渲染器，每批保持编译与快照测试通过
- [x] 自研渲染器文件保留，加 `@deprecated` 注释指向替代
- [x] 移除 `TradingViewLayout` 中的遗留调试 `console.log`
- [x] 迁移完成后，确认无生产代码引用自研渲染器（引用清单写入本工单）


---

## 实施记录 (2026-09-27)

**对拍结果（`src/components/shared/markdown-renderer.test.tsx` 顶部矩阵）：**

| 构造 | 自研 MarkdownRenderer | react-markdown + remark-gfm |
| --- | --- | --- |
| 标题 | `<div>` 样式，无 `<hN>` 锚点 | 语义 `<h1>`…`<h4>` |
| 管道表 | OK | OK（th/td/行宽完全一致） |
| 列表 | 纯文本，无 `<ul>/<li>` | `<ul>/<ol>/<li>` |
| 行内强调 | 原样输出 `**加粗**` | `<strong>/<em>/<code>` |

差异结论：**表格等价**，标题/列表/强调为有损 → 统一到 react-markdown。

**改动清单：**
- 新增 `src/components/shared/Markdown.tsx` — 唯一活跃渲染器（react-markdown + remark-gfm + `prose-compact` 主题 + 表格横向滚动）
- 新增 `.prose-compact` 主题（`src/index.css`），紧凑版（12px，用于 320px 面板条），与报告页 `.prose-report` 并存
- 迁移调用点 **23 个文件**：`astock/MarkdownRenderer` → `shared/Markdown`
- `src/components/astock/MarkdownRenderer.tsx` 保留为 `@deprecated` 薄委托（保留文件，未删除）
- `src/components/shared/index.ts` 导出 `Markdown` 并保留 `MarkdownRenderer` 兼容别名
- 移除 `TradingViewLayout.tsx` 两处遗留调试 `console.log`（第 331/334 行）

**生产代码引用自研渲染器清单：** 无（仅 `markdown-equivalence.test.tsx` 为验证委托而 import 之）。

**验证：** `tsc --noEmit` 0 错误；`vitest run` 7 文件 113 测试全通过（新增 18 个）。
