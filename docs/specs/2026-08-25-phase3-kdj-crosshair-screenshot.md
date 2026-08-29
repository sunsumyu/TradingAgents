# Phase 3: KDJ 副图 + 十字光标增强 + 截图导出 实现规格

> 优先级：P2-P3 | 参考：TradingView / 同花顺 / 东方财富
>
> 日期：2026-08-25

---

## 1. KDJ 副图面板

### 1.1 背景

`KlineChart.tsx` 已有 KDJ 副图实现（使用 ECharts line chart + markLine），
但 `TradingViewLayout.tsx` 的 `SubPanels` 不显示 KDJ。
后端 `schemas.py` 中 `KlineData` 已包含 `kdj_k`, `kdj_d`, `kdj_j` 字段。

### 1.2 目标

在 `SubPanels` 中添加 `KdjMini` 组件，与 MACD/RSI/Bollinger 并列显示。

### 1.3 UI 设计

```
┌─ KDJ ──────────────────────────────┐
│  K: 65.3  D: 58.1  J: 79.7         │  ← 最新值标签
│  ┌─────────────────────────────┐   │
│  │  ╱╲    ╱╲                   │   │
│  │ ╱  ╲  ╱  ╲  ╱╲             │   │  ← K(蓝) D(黄) J(紫)
│  │╱    ╲╱    ╲╱  ╲            │   │
│  │─────────80─────────────────│   │  ← 80 超买线 (红)
│  │                           │   │
│  │─────────20─────────────────│   │  ← 20 超卖线 (绿)
│  └─────────────────────────────┘   │
└────────────────────────────────────┘
```

### 1.4 组件实现

```typescript
// TradingViewLayout.tsx 中新增 KdjMini
function KdjMini({ data, crosshairTime }: { data: KlineData; crosshairTime?: string | null }) {
  const chartRef = useRef<any>(null);

  // Crosshair sync（与 MacdMini/RsiMini 相同模式）
  useEffect(() => {
    const inst = chartRef.current?.getEchartsInstance?.();
    if (!inst || !crosshairTime || !data.kdj_k) return;
    const idx = data.dates.indexOf(crosshairTime);
    if (idx >= 0) inst.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: idx });
    else inst.dispatchAction({ type: "hideTip" });
  }, [crosshairTime, data.dates, data.kdj_k]);

  const option = {
    animation: false,
    grid: { left: 50, right: 10, top: 20, bottom: 20 },
    tooltip: { trigger: "axis" as const },
    xAxis: {
      type: "category" as const,
      data: data.dates,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { show: false },
    },
    yAxis: {
      min: 0, max: 100,
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 9 },
      splitLine: { lineStyle: { color: "#1E222D" } },
    },
    series: [
      { name: "K", type: "line", data: data.kdj_k, lineStyle: { width: 1.2, color: "#2962FF" }, symbol: "none" },
      { name: "D", type: "line", data: data.kdj_d, lineStyle: { width: 1.2, color: "#F7B731" }, symbol: "none" },
      {
        name: "J", type: "line", data: data.kdj_j,
        lineStyle: { width: 1.2, color: "#E040FB" }, symbol: "none",
        markLine: {
          silent: true, symbol: "none",
          lineStyle: { type: "dashed", width: 1 },
          data: [
            { yAxis: 80, lineStyle: { color: "#F23645" }, label: { formatter: "80", color: "#F23645", fontSize: 9 } },
            { yAxis: 20, lineStyle: { color: "#089981" }, label: { formatter: "20", color: "#089981", fontSize: 9 } },
          ],
        },
      },
    ],
  };

  return (
    <div className="relative">
      <span className="absolute top-1 left-2 text-[9px] text-[#787B86] z-10">KDJ</span>
      <ReactECharts ref={chartRef} option={option} style={{ height: "100%", width: "100%" }} notMerge />
    </div>
  );
}
```

### 1.5 SubPanels 修改

```typescript
// TradingViewLayout.tsx
function SubPanels({
  macd, rsi, bollinger, kdj, crosshairTime,
}: {
  macd?: MacdData | null;
  rsi?: RsiData | null;
  bollinger?: BollingerData | null;
  kdj?: KlineData | null;  // 新增：传入完整 kline 数据
  crosshairTime?: string | null;
}) {
  const panels = [macd, rsi, bollinger, kdj].filter(Boolean).length;
  if (panels === 0) return null;

  return (
    <div className="border-t border-[#2B2B43] bg-[#131722]" style={{ height: panels > 2 ? 180 : 140 }}>
      <div className="grid h-full gap-0" style={{ gridTemplateColumns: `repeat(${panels}, 1fr)` }}>
        {macd && <MacdMini data={macd} crosshairTime={crosshairTime} />}
        {rsi && <RsiMini data={rsi} crosshairTime={crosshairTime} />}
        {bollinger && <BollingerMini data={bollinger} crosshairTime={crosshairTime} />}
        {kdj && <KdjMini data={kdj} crosshairTime={crosshairTime} />}
      </div>
    </div>
  );
}
```

### 1.6 验收标准

- [ ] KDJ 面板显示在 SubPanels 中（当有数据时）
- [ ] K/D/J 三线颜色正确（蓝/黄/紫）
- [ ] 80/20 超买超卖线显示
- [ ] 光标联动与 MACD/RSI 一致
- [ ] 无 KDJ 数据时不显示面板

---

## 2. 十字光标 Y 轴价格标签增强

### 2.1 背景

当前 ECharts tooltip 的 `axisPointer.type: "cross"` 已实现基础十字光标，
但 Y 轴没有 TradingView 风格的价格标签（带背景色的矩形标签随光标移动）。

### 2.2 目标行为

- 右侧 Y 轴显示当前光标所在价格的矩形标签（红涨绿跌背景色）
- 底部 X 轴显示当前光标所在日期的矩形标签
- 标签始终可见，随光标移动而移动

### 2.3 实现

在 `TradingViewChart.tsx` 的 ECharts option 中添加 axisPointer label：

```typescript
yAxis: [
  {
    // ... existing config
    axisPointer: {
      label: {
        show: true,
        backgroundColor: (params: any) => {
          // 根据当前价格与前收盘价比较决定红/绿
          const price = params.value;
          const lastClose = ohlc[ohlc.length - 1][1];
          return price >= lastClose ? "#089981" : "#F23645";
        },
        color: "#FFFFFF",
        fontSize: 11,
        fontFamily: "monospace",
        formatter: (value: number) => value.toFixed(2),
        padding: [4, 8],
      },
    },
  },
  // ... volume yAxis
],
xAxis: [
  {
    // ... existing config
    axisPointer: {
      label: {
        show: true,
        backgroundColor: "#2962FF",
        color: "#FFFFFF",
        fontSize: 10,
      },
    },
  },
  // ... volume xAxis
],
```

### 2.4 验收标准

- [ ] Y 轴价格标签随光标移动
- [ ] 价格标签背景色红涨绿跌
- [ ] X 轴日期标签显示当前日期
- [ ] 标签文字清晰可读

---

## 3. 图表截图导出

### 3.1 背景

参考 TradingView 的图表截图功能，用户可将当前图表保存为 PNG 图片。

### 3.2 目标行为

- 工具栏添加截图按钮（相机图标）
- 截取当前 ECharts 图表为 PNG 图片（2x 像素密度）
- 通过浏览器下载或 Tauri 对话框保存到本地

### 3.3 实现

```typescript
// TradingViewLayout.tsx
import { Camera } from "lucide-react";

const handleScreenshot = useCallback(() {
  // 获取 ECharts 实例
  const chartContainer = document.querySelector("[data-chart-container]");
  if (!chartContainer) return;

  // 通过 echarts.getInstanceByDom 获取实例
  const echarts = await import("echarts");
  const instance = echarts.getInstanceByDom(chartContainer as HTMLElement);
  if (!instance) return;

  const url = instance.getDataURL({
    type: "png",
    pixelRatio: 2,
    backgroundColor: "#131722",
  });

  // 创建下载链接
  const link = document.createElement("a");
  link.href = url;
  link.download = `${ticker}_chart_${new Date().toISOString().slice(0, 10)}.png`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}, [ticker]);
```

### 3.4 UI 集成

在 `TradingViewLayout` 的工具栏区域添加截图按钮：
```tsx
<div className="flex items-center gap-1 px-2">
  {/* 截图按钮 */}
  <button
    onClick={handleScreenshot}
    className="p-1.5 rounded hover:bg-[#2A2E39] transition-colors"
    title="截图导出"
  >
    <Camera size={14} className="text-[#787B86]" />
  </button>
</div>
```

### 3.5 验收标准

- [ ] 截图按钮显示在工具栏中
- [ ] 点击后下载 PNG 文件
- [ ] 截图包含完整的 K 线图 + 成交量 + 均线
- [ ] 图片背景色为 #131722（深色主题）
- [ ] 图片分辨率为 2x（Retina 清晰）

---

## 4. 全屏图表模式

### 4.1 目标行为

- 工具栏添加全屏按钮（Maximize2 图标）
- 图表占满整个窗口（隐藏 Watchlist、SubPanels 等）
- ESC 退出全屏

### 4.2 实现

```typescript
// TradingViewLayout.tsx
import { Maximize2, Minimize2 } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

const [isFullscreen, setIsFullscreen] = useState(false);

useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if (e.key === "Escape" && isFullscreen) {
      setIsFullscreen(false);
    }
  };
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
}, [isFullscreen]);
```

### 4.3 布局切换

```tsx
return (
  <div className="flex flex-col h-full bg-[#131722]">
    <ChartHeader ... />

    {isFullscreen ? (
      // 全屏模式：仅显示图表
      <div className="flex-1 min-h-0 relative">
        <TradingViewChart data={kline} activeTool={activeTool} />
        <DrawingOverlay activeTool={activeTool} />
      </div>
    ) : (
      // 正常模式：完整布局
      <div className="flex flex-1 min-h-0">
        <DrawingToolbar ... />
        <div className="flex flex-col flex-1 min-w-0">
          <TimeframeSelector ... />
          <div className="flex-1 min-h-0 relative">
            <TradingViewChart ... />
            <DrawingOverlay ... />
          </div>
          <SubPanels ... />
        </div>
        <div className="w-[220px] flex-shrink-0">
          <WatchlistPanel ... />
        </div>
      </div>
    )}
  </div>
);
```

### 4.4 验收标准

- [ ] 全屏按钮显示在工具栏中
- [ ] 点击后图表占满窗口
- [ ] ESC 键退出全屏
- [ ] 全屏模式下仍可切换时间周期
- [ ] 全屏模式下仍可使用绘图工具

---

## 5. 涉及文件汇总

| 文件 | 变更类型 | 功能 |
|------|---------|------|
| `src/components/tradingview/TradingViewLayout.tsx` | 修改 | KDJ副图 + 全屏 + 截图按钮 |
| `src/components/tradingview/TradingViewChart.tsx` | 修改 | Y轴价格标签 + X轴日期标签 |
| `src/components/tradingview/DrawingOverlay.tsx` | 修改 | 截图功能集成 |
| `src/lib/chart-utils.ts` | 新建 | 共享指标配置 |
