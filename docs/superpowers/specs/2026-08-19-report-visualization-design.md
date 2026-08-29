# Report Visualization Design

**Date**: 2026-08-19
**Status**: Draft
**Scope**: TradingAgents 报告可视化增强

## 1. 目标

将当前纯文本的分析报告升级为包含交互式图表和数据动画的可视化报告，覆盖 GUI 内展示和 HTML 导出两个场景。

## 2. 技术选型

**图表库**: Apache ECharts

理由：
- 原生支持金融图表（K线、MACD、RSI、布林带等）
- 中文生态好，文档丰富
- 内置数据驱动动画
- 一个库覆盖所有图表类型

## 3. 架构设计

### 3.1 数据流

```
后端 (Python)                    前端 (React + ECharts)
┌─────────────────┐            ┌──────────────────────────┐
│ runner.py        │            │ ReportPanel.tsx           │
│ 收集分析结果     │──Report──▶│                          │
│                 │  Response  │ ┌─ ReportCharts.tsx ──┐  │
│ 新增: chart_data│            │ │  K线图 / 技术指标图  │  │
│ (结构化数据)     │            │ │  信号仪表盘         │  │
└─────────────────┘            │ │  资金流向图         │  │
                               │ └────────────────────┘  │
                               │                          │
                               │ saveHtml()               │
                               │ → 内联 ECharts JS       │
                               │ → 独立交互式 HTML       │
                               └──────────────────────────┘
```

### 3.2 数据结构

#### Python 端 (Pydantic)

```python
# tradingagents_api/schemas.py 新增

class KlineData(BaseModel):
    dates: list[str]                    # ["2026-07-01", ...]
    ohlc: list[tuple[float, float, float, float]]  # [(open, close, low, high), ...]
    volumes: list[float]
    ma5: list[float | None] = []
    ma10: list[float | None] = []
    ma20: list[float | None] = []
    ma50: list[float | None] = []

class MacdData(BaseModel):
    dates: list[str]
    macd: list[float]
    signal: list[float]
    histogram: list[float]

class RsiData(BaseModel):
    dates: list[str]
    values: list[float]

class BollingerData(BaseModel):
    dates: list[str]
    upper: list[float]
    middle: list[float]
    lower: list[float]
    close: list[float]

class DashboardData(BaseModel):
    signal: str  # Buy | Hold | Sell | Overweight | Underweight
    confidence: float  # 0-100
    scores: list[dict]  # [{name, value, max}, ...]

class FundFlowData(BaseModel):
    dates: list[str]
    northbound: list[float]
    mainForce: list[float]
    retail: list[float]

class ChartData(BaseModel):
    kline: KlineData | None = None
    macd: MacdData | None = None
    rsi: RsiData | None = None
    bollinger: BollingerData | None = None
    dashboard: DashboardData | None = None
    fundFlow: FundFlowData | None = None
```

#### TypeScript 端

```typescript
// tradingagents_gui/src/lib/types.ts 扩展

interface ChartData {
  kline?: {
    dates: string[];
    ohlc: [number, number, number, number][];
    volumes: number[];
    ma5?: (number | null)[];
    ma10?: (number | null)[];
    ma20?: (number | null)[];
    ma50?: (number | null)[];
  };
  macd?: {
    dates: string[];
    macd: number[];
    signal: number[];
    histogram: number[];
  };
  rsi?: {
    dates: string[];
    values: number[];
  };
  bollinger?: {
    dates: string[];
    upper: number[];
    middle: number[];
    lower: number[];
    close: number[];
  };
  dashboard?: {
    signal: "Buy" | "Hold" | "Sell" | "Overweight" | "Underweight";
    confidence: number;
    scores: { name: string; value: number; max: number }[];
  };
  fundFlow?: {
    dates: string[];
    northbound: number[];
    mainForce: number[];
    retail: number[];
  };
}
```

## 4. 图表组件设计

### 4.1 K线/价格图 (KlineChart)

**布局**: 蜡烛图 + 成交量柱状图（上下分区联动）

**功能**:
- 蜡烛图 + 成交量柱状图（上下分区联动）
- MA5/MA10/MA20/MA50 均线叠加（可选显示）
- 鼠标悬停显示 OHLCV 数据
- 支持缩放和拖拽

**ECharts 配置要点**:
- 使用 `grid` 组件实现上下分区
- 蜡烛图用 `series.type: 'candlestick'`
- 成交量用 `series.type: 'bar'`
- 均线用 `series.type: 'line'`
- 使用 `dataZoom` 实现缩放

### 4.2 MACD 图 (MacdChart)

**布局**: 柱状图（histogram）+ 双线（MACD线 + 信号线）

**功能**:
- 柱状图红绿交替（正值红色，负值绿色）
- MACD线和信号线交叉标注
- 柱状图有展开动画

### 4.3 RSI 图 (RsiChart)

**布局**: 面积图 + 超买/超卖区域标注

**功能**:
- 面积图展示RSI值
- 70/30 水平线标注超买/超卖区域
- 区域用半透明色填充（超买红色，超卖绿色）

### 4.4 布林带图 (BollingerChart)

**布局**: 三轨线 + 中间区域填充

**功能**:
- 上轨、中轨、下轨三条线
- 上下轨之间用半透明色填充
- 当前价格用特殊标记（圆点或竖线）

### 4.5 信号仪表盘 (SignalDashboard)

**布局**: 仪表盘（gauge）+ 雷达图

**功能**:
- 中心大仪表盘显示最终信号（颜色编码：Buy绿色，Sell红色，Hold灰色）
- 雷达图展示各维度评分（技术分析、情绪、基本面、消息面）
- 数字滚动动画展示评分
- 仪表盘指针旋转动画

### 4.6 资金流向图 (FundFlowChart)

**布局**: 堆叠柱状图

**功能**:
- 堆叠柱状图展示每日资金流向
- 北向/主力/散户用不同颜色区分
- 悬停显示具体金额

## 5. HTML 导出方案

### 5.1 导出结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{ticker} 分析报告</title>
  <style>/* 内联样式 */</style>
</head>
<body>
  <h1>{ticker} 分析报告</h1>
  <p>信号: {signal} | 生成时间: {timestamp}</p>
  <hr>

  <!-- 图表区域 -->
  <div id="charts">
    <div id="dashboard"></div>
    <div id="kline"></div>
    <div id="macd"></div>
    <div id="rsi"></div>
    <div id="bollinger"></div>
    <div id="fundflow"></div>
  </div>

  <!-- Markdown 报告 -->
  <div id="report">
    {report_md 转换为 HTML}
  </div>

  <!-- ECharts 库 -->
  <script>{echarts.min.js 内联}</script>

  <!-- 图表初始化脚本 -->
  <script>
    const chartData = {JSON.stringify(chartData)};
    // 初始化各图表...
  </script>
</body>
</html>
```

### 5.2 文件大小预估

| 组件 | 大小 |
|------|------|
| ECharts.min.js | ~1MB |
| 图表数据 JSON | ~50KB |
| 样式 + 报告文本 | ~100KB |
| **总计** | **~1.2MB** |

### 5.3 导出流程改动

```typescript
// ReportPanel.tsx saveHtml() 改动

async saveHtml(report: ReportResponse) {
  const echartsJs = await fetchEchartsMinJs(); // 获取 ECharts 库
  const chartConfig = generateChartConfigs(report.chartData); // 生成图表配置

  const html = `
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
      <meta charset="UTF-8">
      <title>${report.ticker} 分析报告</title>
      <style>${reportStyles}</style>
    </head>
    <body>
      <h1>${report.ticker} 分析报告</h1>
      <p>信号: ${report.signal} | 生成时间: ${new Date().toLocaleString("zh-CN")}</p>
      <hr>
      <div id="charts">${chartContainersHtml}</div>
      <div id="report">${markdownToHtml(report.report_md)}</div>
      <script>${echartsJs}</script>
      <script>${chartConfig}</script>
    </body>
    </html>
  `;

  await saveFile(html);
}
```

## 6. 数据动画效果

| 动画类型 | 应用位置 | 实现方式 |
|---------|---------|---------|
| 数字滚动 | 评分、价格 | ECharts `animationDuration` + 自定义 formatter |
| 柱状图填充 | MACD histogram | ECharts `animationDelay` 逐个展开 |
| 面积渐变 | RSI、布林带 | ECharts `areaStyle.color` 渐变 |
| 仪表盘指针旋转 | 信号仪表盘 | ECharts gauge `animationDuration` |

## 7. 实施计划

### 阶段 1: 后端数据准备

**文件改动**:
- `tradingagents_api/schemas.py` — 新增 `ChartData` Pydantic 模型
- `tradingagents_api/runner.py` — 在分析完成后构建 `chart_data`
  - 从 `final_state` 提取价格数据和技术指标
  - 调用数据工具获取历史数据
  - 组装成 `ChartData` 结构

### 阶段 2: 前端图表组件

**新文件**:
- `tradingagents_gui/src/components/ReportCharts.tsx` — 图表容器组件
- `tradingagents_gui/src/components/charts/KlineChart.tsx`
- `tradingagents_gui/src/components/charts/MacdChart.tsx`
- `tradingagents_gui/src/components/charts/RsiChart.tsx`
- `tradingagents_gui/src/components/charts/BollingerChart.tsx`
- `tradingagents_gui/src/components/charts/SignalDashboard.tsx`
- `tradingagents_gui/src/components/charts/FundFlowChart.tsx`

**改动文件**:
- `tradingagents_gui/package.json` — 添加 `echarts` + `echarts-for-react`
- `tradingagents_gui/src/components/ReportPanel.tsx` — 集成 `ReportCharts`

### 阶段 3: HTML 导出增强

**改动文件**:
- `tradingagents_gui/src/components/ReportPanel.tsx` — 重写 `saveHtml()`

### 阶段 4: 动画与优化

- 添加数据驱动动画
- 响应式布局适配
- 性能优化（图表懒加载）

## 8. 待确认事项

- [ ] ECharts 版本选择（最新 v5.x）
- [ ] 导出 HTML 是否需要离线可用（是，内联 ECharts）
- [ ] 图表是否需要导出为图片功能（可后续添加）
- [ ] 移动端适配优先级
