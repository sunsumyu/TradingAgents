# Phase 3: 绘图撤销/重做 + 副图指标切换 实现规格

> 优先级：P2-P3 | 参考：TradingView / 同花顺
>
> 日期：2026-08-25

---

## 1. 绘图工具撤销/重做

### 1.1 背景

当前 `DrawingOverlay.tsx` 支持趋势线/水平线/矩形/斐波那契的绘制，
但没有撤销/重做功能。参考 TradingView，Ctrl+Z 撤销、Ctrl+Y 重做是标配。

### 1.2 目标行为

| 操作 | 行为 |
|------|------|
| Ctrl+Z / Cmd+Z | 撤销上一次绘图 |
| Ctrl+Y / Cmd+Y | 重做上一次撤销的绘图 |
| 双击图表 | 清空所有绘图（已有） |
| 切换标的 | 清空绘图（新标的数据不同） |

### 1.3 数据模型

```typescript
interface DrawingState {
  drawings: DrawingShape[];     // 当前绘图列表
  history: DrawingShape[][];    // 撤销历史栈
  future: DrawingShape[][];     // 重做历史栈
}
```

### 1.4 实现

```typescript
// DrawingOverlay.tsx
const [drawings, setDrawings] = useState<DrawingShape[]>([]);
const [history, setHistory] = useState<DrawingShape[][]>([]);
const [future, setFuture] = useState<DrawingShape[][]>([]);

// 添加新绘图时，清空 future（新的操作覆盖重做栈）
const handleAddDrawing = useCallback((shape: DrawingShape) => {
  setHistory(prev => [...prev, drawings]);
  setFuture([]);
  setDrawings(prev => [...prev, shape]);
}, [drawings]);

// 撤销
const undo = useCallback(() => {
  if (history.length === 0) return;
  setFuture(prev => [...prev, drawings]);
  setDrawings(history[history.length - 1]);
  setHistory(prev => prev.slice(0, -1));
}, [history, drawings]);

// 重做
const redo = useCallback(() => {
  if (future.length === 0) return;
  setHistory(prev => [...prev, drawings]);
  setDrawings(future[future.length - 1]);
  setFuture(prev => prev.slice(0, -1));
}, [future, drawings]);

// 清空（双击或切换标的）
const clearAll = useCallback(() => {
  if (drawings.length === 0) return;
  setHistory(prev => [...prev, drawings]);
  setFuture([]);
  setDrawings([]);
}, [drawings]);

// 键盘监听
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
      e.preventDefault();
      undo();
    }
    if ((e.ctrlKey || e.metaKey) && (e.key === "y" || (e.key === "z" && e.shiftKey))) {
      e.preventDefault();
      redo();
    }
  };
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
}, [undo, redo]);

// 切换标的时清空绘图
useEffect(() => {
  setDrawings([]);
  setHistory([]);
  setFuture([]);
}, [/* ticker prop */]);
```

### 1.5 性能考虑

- history 栈最大深度限制为 50 步：
  ```typescript
  const MAX_HISTORY = 50;
  setHistory(prev => [...prev.slice(-MAX_HISTORY + 1), drawings]);
  ```
- 避免在每次鼠标移动时创建新对象（仅在 mouseUp 时记录）

### 1.6 验收标准

- [ ] 绘制趋势线后按 Ctrl+Z 可撤销
- [ ] 撤销后按 Ctrl+Y 可重做
- [ ] 绘制多个图形后连续 Ctrl+Z 逐步撤销
- [ ] 撤销后绘制新图形，重做栈清空
- [ ] 切换标的后所有绘图清空
- [ ] history 栈不超过 50 步

---

## 2. 副图指标切换

### 2.1 背景

当前 `SubPanels` 固定显示 MACD/RSI/Bollinger（如果有数据），
用户无法选择显示哪个指标。参考 TradingView/东方财富，副图应支持指标切换。

### 2.2 目标行为

```
┌─ MACD ── [▼] ──────────────────────┐
│  MACD: 0.12  Signal: 0.08           │  ← 点击 [▼] 弹出指标选择菜单
│  ┌─────────────────────────────┐   │
│  │  ▓▓  ▓▓▓                    │   │
│  │  ▓▓  ▓▓▓  ░░░              │   │  ← MACD 柱状图
│  └─────────────────────────────┘   │
└────────────────────────────────────┘

菜单选项：MACD | RSI | Bollinger | KDJ | WR | CCI
```

### 2.3 数据模型

```typescript
interface SubPanelConfig {
  id: string;           // "macd" | "rsi" | "bollinger" | "kdj" | "wr" | "cci"
  label: string;        // "MACD" | "RSI" | "Bollinger" | "KDJ" | "WR" | "CCI"
  available: boolean;   // 是否有数据
}

interface SubPanelState {
  panel1: string;       // 第一个副图显示的指标
  panel2: string;       // 第二个副图显示的指标
  panel3: string;       // 第三个副图显示的指标
}
```

### 2.4 实现

#### 2.4.1 SubPanelHeader 组件

```typescript
// tradingview/SubPanelHeader.tsx
interface Props {
  label: string;
  options: { key: string; label: string; available: boolean }[];
  onSelect: (key: string) => void;
}

export default function SubPanelHeader({ label, options, onSelect }: Props) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="flex items-center gap-1 px-2 py-1 border-b border-[#2B2B43]">
      <span className="text-[9px] text-[#787B86]">{label}</span>
      <button
        onClick={() => setShowMenu(!showMenu)}
        className="text-[9px] text-[#787B86] hover:text-[#D1D4DC] transition-colors"
      >
        ▼
      </button>
      {showMenu && (
        <div className="absolute top-full left-0 z-20 bg-[#1E222D] border border-[#2B2B43] rounded shadow-lg py-1">
          {options.map(opt => (
            <button
              key={opt.key}
              onClick={() => { onSelect(opt.key); setShowMenu(false); }}
              disabled={!opt.available}
              className="block w-full text-left px-3 py-1 text-[10px] hover:bg-[#2A2E39] disabled:opacity-30"
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

#### 2.4.2 TradingViewLayout 状态管理

```typescript
// TradingViewLayout.tsx
const [subPanelConfig, setSubPanelConfig] = useState({
  panel1: "macd",
  panel2: "rsi",
  panel3: "bollinger",
});

const availableIndicators = useMemo(() => [
  { key: "macd", label: "MACD", available: !!macd },
  { key: "rsi", label: "RSI", available: !!rsi },
  { key: "bollinger", label: "Bollinger", available: !!bollinger },
  { key: "kdj", label: "KDJ", available: !!(kline?.kdj_k?.length) },
], [macd, rsi, bollinger, kline]);
```

#### 2.4.3 条件渲染

```typescript
// 根据 subPanelConfig 动态渲染
const panels = [
  { key: subPanelConfig.panel1, data: getIndicatorData(subPanelConfig.panel1) },
  { key: subPanelConfig.panel2, data: getIndicatorData(subPanelConfig.panel2) },
  { key: subPanelConfig.panel3, data: getIndicatorData(subPanelConfig.panel3) },
].filter(p => p.data != null);

function getIndicatorData(key: string) {
  switch (key) {
    case "macd": return macd;
    case "rsi": return rsi;
    case "bollinger": return bollinger;
    case "kdj": return kline?.kdj_k?.length ? kline : null;
    default: return null;
  }
}
```

### 2.5 后端新增指标（WR/CCI）

当前后端不支持 WR 和 CCI。两种路径：

**路径 A：前端计算（推荐，快速实现）**

```typescript
// lib/indicators.ts
export function computeWR(highs: number[], lows: number[], closes: number[], period = 14): number[] {
  const result: number[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { result.push(50); continue; }
    const sliceH = highs.slice(i - period + 1, i + 1);
    const sliceL = lows.slice(i - period + 1, i + 1);
    const hh = Math.max(...sliceH);
    const ll = Math.min(...sliceL);
    const wr = hh === ll ? 50 : ((hh - closes[i]) / (hh - ll)) * 100;
    result.push(wr);
  }
  return result;
}

export function computeCCI(highs: number[], lows: number[], closes: number[], period = 20): number[] {
  const tp = closes.map((c, i) => (highs[i] + lows[i] + c) / 3);
  const result: number[] = [];
  for (let i = 0; i < tp.length; i++) {
    if (i < period - 1) { result.push(0); continue; }
    const slice = tp.slice(i - period + 1, i + 1);
    const sma = slice.reduce((a, b) => a + b, 0) / period;
    const meanDev = slice.reduce((a, b) => a + Math.abs(b - sma), 0) / period;
    const cci = meanDev === 0 ? 0 : (tp[i] - sma) / (0.015 * meanDev);
    result.push(cci);
  }
  return result;
}
```

**路径 B：后端计算（长期方案）**

```python
# chart_data.py
def compute_wr(closes, highs, lows, period=14):
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(50.0)
            continue
        hh = max(highs[i-period+1:i+1])
        ll = min(lows[i-period+1:i+1])
        wr = 50.0 if hh == ll else (hh - closes[i]) / (hh - ll) * 100
        result.append(wr)
    return result
```

### 2.6 验收标准

- [ ] 副图右上角有下拉菜单按钮
- [ ] 点击弹出指标选择菜单
- [ ] 菜单中不可用的指标（无数据）显示为灰色
- [ ] 选择新指标后副图内容切换
- [ ] 默认显示 MACD/RSI/Bollinger
- [ ] 切换后保持布局不变（3 列网格）

---

## 3. 涉及文件汇总

| 文件 | 变更类型 | 功能 |
|------|---------|------|
| `src/components/tradingview/DrawingOverlay.tsx` | 修改 | 撤销/重做 + 历史栈 |
| `src/components/tradingview/SubPanelHeader.tsx` | 新建 | 副图指标选择下拉菜单 |
| `src/components/tradingview/TradingViewLayout.tsx` | 修改 | SubPanels 动态渲染 + 副图状态管理 |
| `src/lib/indicators.ts` | 新建 | WR/CCI 前端计算 |
| `src/lib/chart-utils.ts` | 修改 | 新增 WR/CCI 图表配置 |
