# 05 — 通用表渲染组件 `GenericDataTable`

**What to build:** 一个列定义驱动的通用表组件，消费统一 payload（`{columns, rows, meta}`）即可渲染出表格，含数值单位/格式化、排序、分页、空态与「raw 降级」提示。目标是让后续每个数据面板只需给出列定义与样式，而不是各写一遍表格代码。

**Blocked by:** 02 — 统一 feature payload 契约

**Status:** done (2026-09-27)

- [x] 组件接受 `columns`/`rows`/`meta`，按 `format`/`unit` 渲染单元格
- [x] 支持排序、分页（默认每页 50）、加载态、空态
- [x] `kind: "raw"` 时渲染 markdown 并显示「未结构化」提示
- [x] 组件级单测：列定义缺失、空 rows、数值格式化、raw 降级
- [x] 至少一个真实 feature 接入作为样板（可与 06 协同）


---

## 实施记录 (2026-09-27)

**新增文件：**
- `src/components/shared/GenericDataTable.tsx` — 列定义驱动的通用表
  - `GenericDataTable`（底层：columns/rows/provenance/kind/rawMd）
  - `FeatureDataTable`（适配器：接收后端 `{items,total}` 容器或 payload，走 `rowsFromData`）
  - 单元格经 `formatFeatureCell`（ticket 02 契约：unit + format，渲染器**不推断**）
  - 排序（点表头，数值/文本比较，单位列默认右对齐）、分页（默认 50/页）、加载态、空态
  - `kind:"raw"` 或列为空 → `Markdown` 渲染 + 「未结构化」提示条
  - `provenance.source / as_of` 显示为数据源注脚
- `src/components/shared/GenericDataTable.test.tsx` — 17 测试：列定义、格式化（percent/signed/float2/空值破折号）、颜色、空态、加载态、raw 降级、provenance、分页（1/3 页）、单位对齐、`rowsFromData` 适配
- `src/components/shared/index.ts` 导出新组件

**样板接入（验收第 5 条）：** `astock/InstitutionalHoldPanel.tsx` 改为消费 `FeatureDataTable` +
10 列定义（对接 ticket 06 的 `_parse_institutional_hold` 字段），不再自写表格代码。

**验证：** `tsc --noEmit` 0 错误；`vitest run` 8 文件 **130 测试全通过**（新增 17）；后端套件不受影响。
