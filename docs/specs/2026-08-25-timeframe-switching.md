# 时间周期切换功能规格文档

> 日期：2026-08-25
> 状态：Draft
> 优先级：P0
> 驱动方式：文档驱动开发

---

## 1. 问题陈述

当前 GUI 的时间周期选择器（1D / 1W / 1M / 3M / 1Y / ALL）按钮存在但**点击无反应**。

根因：`TimeframeSelector` 组件的 `onChange` 回调只更新了 `TradingViewLayout` 的本地 state（`setTimeframe`），但没有触发数据重新加载。K 线图、MACD、RSI、Bollinger 等数据都是在进入市场数据页面时一次性加载的，切换周期不会重新请求后端。

参考 TradingView 的行为：用户点击不同时间周期时，图表应**立即切换**到对应周期的数据，指标随之重算，整个过程应在 1-3 秒内完成。

## 2. 用户故事

### 2.1 核心切换

1. 作为用户，我点击 "1W" 按钮后，K 线图立即切换为周线数据
2. 作为用户，我点击 "1M" 按钮后，K 线图立即切换为月线数据
3. 作为用户，我点击 "3M" 按钮后，K 线图显示近 3 个月的日线数据
4. 作为用户，我点击 "1Y" 按钮后，K 线图显示近 1 年的日线数据
5. 作为用户，我点击 "ALL" 按钮后，K 线图显示该标的全部可用历史数据
6. 作为用户，我点击 "1D" 按钮后，K 线图恢复为默认的 90 天日线视图

### 2.2 加载体验

7. 作为用户，切换周期时图表区域显示加载指示器（spinner 或骨架屏）
8. 作为用户，切换周期时当前图表数据保持可见直到新数据加载完成（避免闪烁空白）
9. 作为用户，切换周期的响应时间不超过 3 秒（含网络请求）
10. 作为用户，如果新周期数据加载失败，图表保持当前周期数据不变，并显示错误提示
11. 作为用户，快速连续点击不同周期时，只有最后一次点击生效（防抖/竞态处理）

### 2.3 指标联动

12. 作为用户，切换周期后 MACD 指标自动重算为新周期的值
13. 作为用户，切换周期后 RSI 指标自动重算为新周期的值
14. 作为用户，切换周期后 Bollinger Bands 自动重算为新周期的值
15. 作为用户，切换周期后 MA 均线（MA5/MA10/MA20/MA50）自动重算

### 2.4 周期映射

16. 作为用户，"1D" 周期显示最近 90 天的日 K 线（约60 根蜡烛图）
17. 作为用户，"1W" 周期显示最近 180 天的数据
18. 作为用户，"1M" 周期显示最近 365 天的数据
19. 作为用户，"3M" 周期显示最近 730 天的数据
20. 作为用户，"1Y" 周期显示最近 1825 天的数据
21. 作为用户，"ALL" 周期显示最近 3650 天（约 10 年）的数据

### 2.5 状态保持

22. 作为用户，切换周期后十字光标位置重置到最新数据点
23. 作为用户，切换周期后绘图标注（趋势线等）保持不变（如果位置仍在可见范围内）
24. 作为用户，切换周期后 Watchlist 面板内容不变
25. 作为用户，当前选中的周期按钮有高亮视觉反馈

### 2.6 与 TradingView/同花顺对齐的增强功能

26. 作为用户，我希望支持更细粒度的时间周期（如 5m、15m、30m、1h、4h），这些周期显示的是日内分时数据
27. 作为用户，我希望在数据加载期间看到进度提示（如 "正在加载周线数据…"）
28. 作为用户，我希望切换周期后图表的缩放级别自动适配新数据量（不会因为数据太多而挤在一起）
29. 作为用户，我希望按键盘快捷键切换周期（如按 1=1D, 2=1W, 3=1M 等）

## 3. 实现决策

### 3.1 数据流架构

**决策：时间周期切换走 `/api/chart-data` 端点，按需加载**

- 前端 `TradingViewLayout` 在周期切换时调用 `api.getChartData(ticker, date, days)`
- `TIMEFRAME_DAYS` 映射已定义在 `types.ts` 中（1D=90, 1W=180, 1M=365, 3M=730, 1Y=1825, ALL=3650）
- 后端 `/api/chart-data` 已支持 `days` 参数
- 前端需要新增 `api.getChartData()` 函数

### 3.2 状态管理

**决策：将 timeframe 状态提升到 App 层级，或在 TradingViewLayout 内部管理**

方案 A（推荐）：在 `TradingViewLayout` 内部管理
- `TradingViewLayout` 新增内部 state 管理加载状态和当前数据
- 周期切换时调用 `api.getChartData()` 并更新内部 state
- 优点：改动最小，不涉及 App.tsx 的状态管理

方案 B：提升到 App 层级
- 将 timeframe 和 chartData 放到 App.tsx
- 优点：全局可访问
- 缺点：改动大，MarketDataPanel 和 ReportPanel 都需要适配

### 3.3 加载状态处理

**决策：使用局部 loading state + 乐观更新**

- 切换周期时设置 `isLoadingChart=true`
- 显示 loading spinner 覆盖在图表区域
- 数据返回后更新 `kline`/`macd`/`rsi`/`bollinger` 并设置 `isLoadingChart=false`
- 如果请求失败，保持当前数据，显示 toast 错误提示

### 3.4 竞态处理

**决策：使用 AbortController 取消过期请求**

- 每次发起新请求时，取消上一次未完成的请求
- 防止快速切换时返回旧数据覆盖新数据

### 3.5 API 合约

**请求：** `POST /api/chart-data`

```json
{
  "ticker": "600733",
  "date": "2026-08-25",
  "days": 180
}
```

**响应：** 与 `/api/market-data` 类似，返回 `kline`, `macd`, `rsi`, `bollinger`, `fundFlow`

### 3.6 前端 API 函数

在 `api.ts` 中新增：

```typescript
async getChartData(ticker: string, date: string, days: number): Promise<{
  ticker: string;
  date: string;
  days: number;
  kline?: KlineData | null;
  macd?: MacdData | null;
  rsi?: RsiData | null;
  bollinger?: BollingerData | null;
  fundFlow?: FundFlowData | null;
}>
```

### 3.7 组件修改

- `TimeframeSelector`：保持不变（已正确触发 onChange）
- `TradingViewLayout`：新增 `fetchChartData(tf: Timeframe)` 方法，周期切换时调用
- `TradingViewChart`：保持不变（已支持动态数据更新）

## 4. 测试决策

### 4.1 测试策略

- **手动测试**：点击不同周期按钮，验证图表数据变化
- **API 测试**：直接调用 `/api/chart-data?days=N` 验证不同 days 参数返回正确数据
- **竞态测试**：快速连续切换周期，验证最终显示的是最后一次选择的数据

### 4.2 验收标准

- [ ] 点击任意周期按钮后，图表在 3 秒内更新
- [ ] 切换周期时显示 loading 指示器
- [ ] 切换周期后 MACD/RSI/Bollinger 指标正确重算
- [ ] 快速切换时不会出现数据错乱
- [ ] 加载失败时保持当前数据并显示错误提示

## 5. 范围外

1. **日内分时数据**（5m/15m/30m/1h/4h）— 需要后端支持分钟级数据聚合，后续迭代
2. **实时数据推送** — WebSocket 实时更新为独立功能
3. **周期预加载** — 预测用户可能切换的周期并提前加载
4. **自定义周期** — 用户自定义任意天数的周期

## 6. 实施计划

### Phase 1：基础功能（本次实现）
1. 在 `api.ts` 中新增 `getChartData()` 函数
2. 修改 `TradingViewLayout` 支持周期切换数据加载
3. 添加 loading 状态和错误处理
4. 添加 AbortController 竞态处理

### Phase 2：增强功能（后续）
1. 支持日内分时周期（5m/15m/30m/1h/4h）
2. 键盘快捷键切换周期
3. 周期切换动画过渡

---

**下一步：** 基于此规格文档实施 Phase 1。
