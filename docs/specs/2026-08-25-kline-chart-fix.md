# K 线图修复规格文档

> 日期：2026-08-25  
> 状态：Draft  
> 优先级：P0 - Critical  
> 关联：2026-08-25-tradingview-quality-gui.md

---

## 1. 问题描述

当前 GUI 的主 K 线图区域显示 "暂无 K 线数据"，但底部的 MACD 和 RSI 子面板有数据显示。这表明：

1. 后端 API 已正确返回 K 线数据
2. 数据已成功加载到前端
3. 但 `TradingViewChart.tsx` 组件未能正确渲染 K 线图

从截图分析：
- 顶部 ticker 信息栏显示 600733，但价格显示 0.00
- MACD 面板显示了柱状图和信号线（有数据）
- RSI 面板显示了 RSI 线和超买超卖区域（有数据）
- 主图区域完全空白

## 2. 根因分析

### 2.1 数据流追踪

```
用户输入 ticker
    ↓
App.tsx 调用 fetchMarketData(ticker, date)
    ↓
api.ts 调用 POST /api/market-data
    ↓
server.py 返回 MarketDataResponse
    ↓
App.tsx 将数据传递给 MarketDataPanel
    ↓
MarketDataPanel 将数据传递给 TradingViewLayout
    ↓
TradingViewLayout 将数据传递给 TradingViewChart
    ↓
TradingViewChart 渲染 K 线图
```

### 2.2 可能的问题点

1. **数据格式不匹配** — 后端返回的数据格式与 `TradingViewChart.tsx` 期望的格式不一致
2. **ECharts 配置错误** — 图表配置项有误导致不渲染
3. **数据为空** — 后端未正确返回 K 线数据
4. **组件渲染问题** — React 组件生命周期或 props 传递问题

### 2.3 代码分析

`TradingViewChart.tsx` 当前使用 ECharts 渲染 K 线图，关键代码：

```typescript
// 期望的数据格式
interface KlineData {
  date: string;      // 或 number
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma5?: number;
  ma10?: number;
  ma20?: number;
  ma50?: number;
  ema12?: number;
  ema26?: number;
}
```

`types.ts` 中定义的 `KlineData`：

```typescript
export interface KlineData {
  date: string;           // ISO 日期字符串
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma5?: number;
  ma10?: number;
  ma20?: number;
  ma50?: number;
  ema12?: number;
  ema26?: number;
  kdj?: { k: number; d: number; j: number };
}
```

`chart_data.py` 中构建的数据：

```python
kline_data = KlineData(
    date=date_str,          # YYYY-MM-DD 格式
    open=float(row['Open']),
    high=float(row['High']),
    low=float(row['Low']),
    close=float(row['Close']),
    volume=int(row['Volume']),
    ma5=ma5_val,
    ma10=ma10_val,
    # ... 其他字段
)
```

### 2.4 假设的根因

**假设 1：ECharts 日期格式问题**

ECharts K 线图的 x 轴需要特定格式的日期数据。如果日期格式不正确，图表不会渲染任何内容。

**假设 2：数据未传递到组件**

`TradingViewChart` 可能没有正确接收到来自父组件的数据 props。

**假设 3：ECharts 配置项错误**

`candlestick` 系列的 `data` 配置可能有误。

## 3. 修复方案

### 3.1 快速修复（P0）

**步骤 1：验证数据是否到达组件**

在 `TradingViewChart.tsx` 中添加调试日志：

```typescript
console.log('TradingViewChart props:', { data, ticker, timeframe });
console.log('KlineData length:', data?.kline?.length);
console.log('First kline item:', data?.kline?.[0]);
```

**步骤 2：修复日期格式**

确保 ECharts 接收到正确格式的日期数据。ECharts K 线图期望：

```typescript
// 方法 1：使用 timestamp
data: klineData.map(item => ({
  value: [item.date, item.open, item.close, item.low, item.high],
  // 或
  value: [new Date(item.date).getTime(), item.open, item.close, item.low, item.high]
}))

// 方法 2：使用 category 轴
xAxis: {
  type: 'category',
  data: klineData.map(item => item.date)  // ['2026-01-01', '2026-01-02', ...]
}
```

**步骤 3：修复数据格式**

确保 K 线数据格式正确：

```typescript
// 正确格式
const formattedData = klineData.map(item => [
  item.open,
  item.close,
  item.low,
  item.high
]);

// 或使用对象格式
const formattedData = klineData.map(item => ({
  name: item.date,
  value: [item.open, item.close, item.low, item.high]
}));
```

### 3.2 完整修复方案

**文件修改清单：**

1. `tradingagents_gui/src/components/charts/TradingViewChart.tsx`
   - 修复数据格式转换
   - 修复日期格式
   - 添加调试日志

2. `tradingagents_api/chart_data.py`
   - 验证数据格式
   - 确保返回完整的 K 线数据

3. `tradingagents_gui/src/components/tradingview/TradingViewLayout.tsx`
   - 验证数据传递

## 4. 验证步骤

1. **手动测试**
   - 输入 ticker 600733
   - 点击 "查看数据" 按钮
   - 检查浏览器控制台是否有调试日志
   - 检查 Network 面板是否有 API 请求
   - 检查 Response 是否包含 kline 数据

2. **自动测试**
   - 编写单元测试验证数据格式转换
   - 编写集成测试验证图表渲染

## 5. 回滚方案

如果修复引入新问题，可以临时回退到 `KlineChart.tsx` 组件（已验证可用）。

## 6. 时间估算

- 调试和定位：2-4 小时
- 实施修复：2-4 小时
- 测试验证：1-2 小时
- **总计：1 天**

---

**下一步：** 开始实施修复，首先添加调试日志确定根因。
