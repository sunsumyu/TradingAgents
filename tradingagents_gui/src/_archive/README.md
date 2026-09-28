# _archive — 无引用组件归档（工单 10，2026-09-27）

这里的文件**没有被删除**，只是从编译路径中移出（`tsconfig.json` exclude 了本目录）。
每个文件归档时都经过全仓引用扫描，确认 0 个生产代码引用。判定依据见
`.scratch/eastmoney-align/issues/10-orphan-components.md`。

| 文件 | 原位置 | 归档原因 |
| --- | --- | --- |
| `components/ReportCharts.tsx` | `src/components/` | 报告页已改用 `TradingViewLayout`（交互式，含 replay/alerts/realtime），本组件的 K线/MACD/RSI/布林 与之重复，且自身 0 引用 |
| `components/charts/KlineChart.tsx` | `src/components/charts/` | 仅被 ReportCharts 引用（连带归档）；交易页使用 lightweight-charts 方案 |
| `components/charts/MacdChart.tsx` | `src/components/charts/` | 同上 |
| `components/charts/RsiChart.tsx` | `src/components/charts/` | 同上 |
| `components/charts/BollingerChart.tsx` | `src/components/charts/` | 同上 |
| `components/DataTable.tsx` | `src/components/shared/DataTable.tsx` | 被工单 05 的 `GenericDataTable` 取代（排序/分页/单位格式化/raw 降级），原文件 0 生产引用 |
| `components/MarkdownTable.tsx` | `src/components/astock/MarkdownTable.tsx` | 0 引用；表格渲染由 `shared/Markdown`（react-markdown）与 `GenericDataTable` 承担 |
| `components/DrawingManager.ts` | `src/components/tradingview/` | 0 引用；lightweight-charts 画线原语从未接线 |

**复活（未归档，接入报告页）：**
- `src/components/charts/SignalDashboard.tsx` — 渲染 `chartData.dashboard`（后端 `_build_dashboard` 产出，此前无任何消费方）
- `src/components/charts/FundFlowChart.tsx` — 渲染 `chartData.fundFlow`（后端 fund_flow 管线产出，此前无任何消费方）

两者已接入 `src/components/ReportPanel.tsx`（TradingViewLayout 下方两张卡片）。

**仍存活、未归档的 charts/ 成员：** `FundamentalCards.tsx`、`NewsFeed.tsx`（MarketDataPanel 在用）、
`SignalDashboard.tsx`、`FundFlowChart.tsx`（ReportPanel 在用）。

如需恢复某个文件：把它移回原位置（表中列出）并从 `tsconfig.json` 的 exclude 中放行即可。
