# 10 — 孤儿组件复活/归档

**What to build:** 存在一批无引用组件：`ReportCharts.tsx` 及其引用的 6 个图表组件（Kline/Macd/Rsi/Bollinger/SignalDashboard/FundFlow）、`astock/MarkdownTable.tsx`、`tradingview/DrawingManager.ts`、`shared/index.ts` + `shared/DataTable.tsx`。优先**复活**有价值的（`ReportCharts` 系列进报告页；`shared/DataTable` 在 05 之后提升为通用表基座或删除重复）；确不复活者移入 `_archive/` 并标注，**不删除**。

**Blocked by:** 05 — 通用表渲染组件（决定 `shared/DataTable` 的去向）

**Status:** done (2026-09-27)

- [x] 逐组件判定「复活 / 归档」，判定依据写入本工单
- [x] `ReportCharts` 系列接入报告页（或明确记录为归档及原因）
- [x] `shared/DataTable` 与 `GenericDataTable` 的关系明确（复用/取代/归档），不保留两份重复实现同时活跃
- [x] 归档组件移入 `_archive/`，保留文件与注释
- [x] 全仓重新扫描无引用组件，结果清零或全部登记


---

## 实施记录 (2026-09-27)

### 逐组件判定（复活 / 归档）

| 组件 | 判定 | 依据 |
| --- | --- | --- |
| `ReportCharts.tsx` | **归档** | 0 引用。报告页已用 `TradingViewLayout`（lightweight-charts，交互式：replay/告警/实时价），其 K线/MACD/RSI/布林与之功能重复 |
| `charts/KlineChart` `MacdChart` `RsiChart` `BollingerChart` | **归档** | 仅被 ReportCharts 引用（连带归档） |
| `charts/SignalDashboard` | **复活** | 渲染 `chartData.dashboard` — 后端 `_build_dashboard` 持续产出，此前**全 GUI 无任何消费方** |
| `charts/FundFlowChart` | **复活** | 渲染 `chartData.fundFlow` — 后端 fund_flow 管线持续产出，此前**全 GUI 无任何消费方** |
| `charts/FundamentalCards` `charts/NewsFeed`（+`market/NewsFeed`） | 保留 | MarketDataPanel / MarketOverviewPage 在用（工单最初误列为孤儿候选，实为存活） |
| `shared/DataTable.tsx` | **归档** | 被工单 05 `GenericDataTable` 取代（排序/分页/单位格式/raw 降级）；原文件 0 生产引用（`formatSigned/formatWanYi/parseMarkdownTable` 亦无人导入） |
| `astock/MarkdownTable.tsx` | **归档** | 0 引用；表格由 `shared/Markdown` 与 `GenericDataTable` 承担 |
| `tradingview/DrawingManager.ts` | **归档** | 0 引用；lightweight-charts 画线原语从未接线 |
| `shared/index.ts` | **保留** | 公共出口；已移除对已归档 DataTable 的导出（含 `MarkdownRenderer` 兼容别名一并清点） |

### 复活实施
`ReportPanel.tsx` 在 TradingViewLayout 下方新增两张卡片（纯新增）：
「信号仪表盘」← `chartData.dashboard`、「资金流向」← `chartData.fundFlow`。

### 归档实施
- 8 个文件移入 `src/_archive/`（**保留原相对结构**，git mv / mv，未删除任何文件）
- `tsconfig.json` 新增 `"exclude": ["src/_archive"]`（归档代码退出编译，不参与 tsc/vite build）
- `src/_archive/README.md` 登记每个文件的归档原因与恢复方法

### 全仓重新扫描（验收第 5 条）
对 `src/**/*.{ts,tsx}`（排除 `_archive`、入口/barrel）做逐文件引用扫描：
**孤儿数 = 0**（唯一命中是 `GenericDataTable.test.tsx` — 测试文件按设计不被 import）。

### 验证
`tsc --noEmit` 0 错误；`vitest run` 8 文件 130 测试全通过；后端套件不受影响。
