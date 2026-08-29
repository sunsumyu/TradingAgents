# Phase 3: 指标参数栏 (IndicatorBar) 实现规格

> 优先级：P2 | 参考：TradingView 指标参数栏 / 同花顺 指标切换栏
>
> 日期：2026-08-25

---

## 1. 背景

当前 `KlineChart.tsx`（报告页面使用的独立 K 线图）已有完整的指标参数栏：
- MA5/MA10/MA20/MA50/EMA12/EMA26 可切换显示/隐藏
- 每个指标显示最新值（如 `MA5 23.45`）
- 颜色编码与线条颜色一致
- KDJ 可独立开关

但 `TradingViewLayout` 中使用的 `TradingViewChart`（市场数据预览页面的主图）
没有参数栏，overlays 硬编码为 `["ma5", "ma10", "ma20", "ma50"]`。

---

## 2. 目标

将指标参数栏从 `KlineChart.tsx` 提取为独立组件 `IndicatorBar.tsx`，
并在 `TradingViewChart` 中集成，实现与 TradingView/同花顺一致的指标切换体验。

---

## 3. UI 设计

### 3.1 布局

```
┌──────────────────────────────────────────────────────────────┐
│ [MA5 23.45] [MA10 23.12] [MA20 22.87] [MA50 22.10] │ [EMA12 —] [EMA26 —] │
└──────────────────────────────────────────────────────────────┘
     ↑ 每个指标 = 可点击按钮，显示指标名 + 最新值
     ↑ 点击 = toggle 显示/隐藏
     ↑ 颜色 = 与 K 线图中线条颜色一致
     ↑ 活跃指标 = 有边框高亮
     ↑ 非活跃指标 = 灰色文字
```

### 3.2 交互

| 操作 | 行为 |
|------|------|
| 左键点击指标 | toggle 显示/隐藏该均线 |
| 右键点击指标 | 弹出参数设置弹窗（Phase 3+） |
| 鼠标悬停 | 高亮显示 |

### 3.3 颜色映射

| 指标 | 颜色 | 来源 |
|------|------|------|
| MA5 | #F7B731 (黄) | chart-theme.ts |
| MA10 | #2962FF (蓝) | chart-theme.ts |
| MA20 | #9B59B6 (紫) | chart-theme.ts |
| MA50 | #26A69A (青) | chart-theme.ts |
| EMA12 | #E040FB (粉) | chart-theme.ts |
| EMA26 | #00BCD4 (青) | chart-theme.ts |

---

## 4. 组件接口

### 4.1 IndicatorBar.tsx

```typescript
interface IndicatorBarProps {
  data: KlineData;                    // K 线数据（用于获取最新值）
  activeOverlays: string[];           // 当前显示的指标列表
  onToggleOverlay: (key: string) => void;  // 切换显示/隐藏
  className?: string;                 // 可选样式类
}
```

### 4.2 指标配置（从 KlineChart 提取）

```typescript
interface IndicatorConfig {
  key: string;           // "MA5" | "MA10" | "MA20" | "MA50" | "EMA12" | "EMA26"
  field: keyof KlineData; // "ma5" | "ma10" | "ma20" | "ma50" | "ema12" | "ema26"
  color: string;
}

const OVERLAY_CONFIG: IndicatorConfig[] = [
  { key: "MA5",   field: "ma5",   color: "#F7B731" },
  { key: "MA10",  field: "ma10",  color: "#2962FF" },
  { key: "MA20",  field: "ma20",  color: "#9B59B6" },
  { key: "MA50",  field: "ma50",  color: "#26A69A" },
  { key: "EMA12", field: "ema12", color: "#E040FB" },
  { key: "EMA26", field: "ema26", color: "#00BCD4" },
];
```

---

## 5. 集成到 TradingViewChart

### 5.1 Props 变更

```typescript
// TradingViewChart.tsx
interface Props {
  data: KlineData | null;
  activeOverlays?: string[];        // 新增：当前显示的 overlays
  onToggleOverlay?: (key: string) => void;  // 新增：toggle 回调
  activeTool?: DrawingTool;
  onCrosshairMove?: (info: CrosshairInfo | null) => void;
}
```

### 5.2 TradingViewLayout 状态管理

```typescript
// TradingViewLayout.tsx
const [activeOverlays, setActiveOverlays] = useState<string[]>(["ma5", "ma10", "ma20", "ma50"]);

const handleToggleOverlay = useCallback((key: string) => {
  setActiveOverlays(prev =>
    prev.includes(key)
      ? prev.filter(k => k !== key)
      : [...prev, key]
  );
}, []);
```

### 5.3 布局调整

```
TradingViewLayout
├── ChartHeader
├── TimeframeSelector
├── DrawingToolbar
├── ┌─ ChartArea ──────────────────────┐
│   │ IndicatorBar (新增)              │  ← 指标参数栏
│   │ TradingViewChart                 │  ← K 线主图
│   │   └── DrawingOverlay             │
│   └──────────────────────────────────┘
├── SubPanels (MACD/RSI/Boll/KDJ)
└── WatchlistPanel
```

---

## 6. 从 KlineChart 提取共享逻辑

### 6.1 需要提取的代码

| 代码段 | 来源 | 目标 |
|--------|------|------|
| `OVERLAY_CONFIG` 常量 | KlineChart.tsx:12-19 | 共享模块 |
| `buildOverlaySeries()` 函数 | KlineChart.tsx:368-384 | 共享模块 |
| `getLatestValue()` 辅助函数 | KlineChart.tsx:47-52 | IndicatorBar 内部 |

### 6.2 共享模块

新建 `tradingagents_gui/src/lib/chart-utils.ts`：
```typescript
import type { KlineData } from "./types";

export const OVERLAY_CONFIG = [
  { key: "MA5",   field: "ma5"   as keyof KlineData, color: "#F7B731" },
  { key: "MA10",  field: "ma10"  as keyof KlineData, color: "#2962FF" },
  { key: "MA20",  field: "ma20"  as keyof KlineData, color: "#9B59B6" },
  { key: "MA50",  field: "ma50"  as keyof KlineData, color: "#26A69A" },
  { key: "EMA12", field: "ema12" as keyof KlineData, color: "#E040FB" },
  { key: "EMA26", field: "ema26" as keyof KlineData, color: "#00BCD4" },
];

export function getLatestIndicatorValue(data: KlineData, field: keyof KlineData): string {
  const arr = data[field] as (number | null)[] | undefined;
  if (!arr || arr.length === 0) return "—";
  const v = arr[arr.length - 1];
  return v != null ? v.toFixed(2) : "—";
}

export function buildOverlaySeries(data: KlineData, activeOverlays: string[]) {
  return OVERLAY_CONFIG
    .filter(({ key }) => activeOverlays.includes(key))
    .filter(({ field }) => {
      const arr = data[field] as (number | null)[] | undefined;
      return arr && arr.length > 0;
    })
    .map(({ key, field, color }) => ({
      name: key,
      type: "line" as const,
      data: data[field] as (number | null)[],
      smooth: true,
      lineStyle: { width: 1.2, color },
      symbol: "none",
      z: 5,
    }));
}
```

---

## 7. 涉及文件

| 文件 | 变更类型 | 变更内容 |
|------|---------|---------|
| `src/lib/chart-utils.ts` | 新建 | 提取共享指标配置和工具函数 |
| `src/components/tradingview/IndicatorBar.tsx` | 新建 | 指标参数栏组件 |
| `src/components/tradingview/TradingViewChart.tsx` | 修改 | 添加 activeOverlays/onToggleOverlay props |
| `src/components/tradingview/TradingViewLayout.tsx` | 修改 | 管理 activeOverlays 状态 + 渲染 IndicatorBar |
| `src/components/charts/KlineChart.tsx` | 修改 | 导入共享模块替代内联代码 |

---

## 8. 验收标准

- [ ] IndicatorBar 显示在 TradingViewChart 上方
- [ ] 点击 MA5 按钮可切换 MA5 均线的显示/隐藏
- [ ] 按钮颜色与 K 线图中线条颜色一致
- [ ] 活跃指标有边框高亮，非活跃指标为灰色
- [ ] 按钮显示指标的最新值（如 `MA5 23.45`）
- [ ] KlineChart 和 TradingViewChart 共享同一套指标配置
- [ ] 切换指标时无需重新获取数据（纯前端过滤）
