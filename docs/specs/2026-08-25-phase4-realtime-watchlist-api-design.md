# Phase 4: 实时价格更新 + 自选股分组 + API 设计

> 优先级：P3-P4 | 参考：TradingView / 东方财富 / 同花顺
>
> 日期：2026-08-25

---

## 1. 实时价格更新

### 1.1 背景

当前价格仅在数据获取时更新，不会实时跳动。
参考 TradingView/东方财富/同花顺，Watchlist 中的价格应实时更新。

### 1.2 目标行为

| 位置 | 行为 |
|------|------|
| WatchlistPanel | 价格每 3-5 秒自动更新 |
| ChartHeader | 价格实时跳动 |
| 涨跌颜色 | 实时变化（红涨绿跌） |
| 最后交易时间 | 显示"实时"或"盘前/盘后"状态 |

### 1.3 后端 API 设计

#### 方案 A：WebSocket（推荐）

```
端点: ws://127.0.0.1:8420/ws/realtime
协议:
  Client → Server: { "tickers": ["600733", "AAPL", "0700.HK"] }
  Server → Client: { "600733": { "price": 12.34, "change": 0.56, "changePct": 4.76, "volume": 1234567 }, ... }
  推送间隔: 3 秒
```

#### 方案 B：HTTP 轮询（简单实现）

```
端点: POST /api/realtime-prices
请求: { "tickers": ["600773", "AAPL"] }
响应: { "600733": { "price": 12.34, "change": 0.56, "changePct": 4.76 }, ... }
前端轮询间隔: 5 秒
```

### 1.4 前端实现

#### 1.4.1 useRealtimePrices Hook

```typescript
// lib/useRealtimePrices.ts
import { useState, useEffect, useRef, useCallback } from "react";

interface RealtimePrice {
  price: number;
  change: number;
  changePct: number;
  volume?: number;
}

export function useRealtimePrices(tickers: string[], enabled: boolean = true) {
  const [prices, setPrices] = useState<Map<string, RealtimePrice>>(new Map());
  const wsRef = useRef<WebSocket | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!enabled || tickers.length === 0) return;

    // 方案 A: WebSocket
    const ws = new WebSocket("ws://127.0.0.1:8420/ws/realtime");
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ tickers }));
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setPrices(new Map(Object.entries(data)));
      } catch { /* ignore */ }
    };

    ws.onerror = () => {
      // 降级到轮询
      startPolling();
    };

    ws.onclose = () => {
      // 重连
      if (enabled) {
        setTimeout(() => {
          if (wsRef.current === ws) startPolling();
        }, 5000);
      }
    };

    // 方案 B: HTTP 轮询（降级方案）
    function startPolling() {
      if (intervalRef.current) return;
      intervalRef.current = setInterval(async () => {
        try {
          const resp = await fetch("http://127.0.0.1:8420/api/realtime-prices", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tickers }),
          });
          if (resp.ok) {
            const data = await resp.json();
            setPrices(new Map(Object.entries(data)));
          }
        } catch { /* ignore */ }
      }, 5000);
    }

    return () => {
      ws.close();
      wsRef.current = null;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [tickers.join(","), enabled]);

  return prices;
}
```

#### 1.4.2 WatchlistPanel 集成

```typescript
// WatchlistPanel.tsx
import { useRealtimePrices } from "../../lib/useRealtimePrices";

export default function WatchlistPanel({ onSelect, currentTicker }: Props) {
  const [items, setItems] = useState<WatchlistItem[]>(loadWatchlist());

  // 获取所有 ticker 用于实时更新
  const tickers = items.map(i => i.ticker);
  const realtimePrices = useRealtimePrices(tickers, true);

  // 合并实时价格到 items
  const enrichedItems = items.map(item => {
    const rt = realtimePrices.get(item.ticker);
    if (!rt) return item;
    return {
      ...item,
      lastPrice: rt.price,
      change: rt.change,
      changePercent: rt.changePct,
    };
  });

  // ... 渲染 enrichedItems
}
```

#### 1.4.3 ChartHeader 集成

```typescript
// ChartHeader.tsx — 价格跳动动画
const priceRef = useRef<HTMLSpanElement>(null);
const prevPrice = useRef(price);

useEffect(() => {
  if (price !== prevPrice.current && priceRef.current) {
    // 闪烁动画
    priceRef.current.style.transition = "none";
    priceRef.current.style.backgroundColor = price > prevPrice.current
      ? "rgba(8,153,129,0.2)" : "rgba(242,54,69,0.2)";
    requestAnimationFrame(() => {
      if (priceRef.current) {
        priceRef.current.style.transition = "background-color 1s";
        priceRef.current.style.backgroundColor = "transparent";
      }
    });
    prevPrice.current = price;
  }
}, [price]);
```

### 1.5 后端实现（server.py）

```python
# server.py
@app.websocket("/ws/realtime")
async def realtime_prices(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        tickers = data.get("tickers", [])

        while True:
            prices = {}
            for ticker in tickers:
                try:
                    # 调用数据源获取实时价格
                    from tradingagents.dataflows import get_realtime_price
                    price_info = await asyncio.get_event_loop().run_in_executor(
                        None, get_realtime_price, ticker
                    )
                    prices[ticker] = price_info
                except Exception:
                    pass

            await websocket.send_json(prices)
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass

# HTTP 降级方案
@app.post("/api/realtime-prices")
async def realtime_prices_http(request: dict):
    tickers = request.get("tickers", [])
    prices = {}
    for ticker in tickers:
        try:
            from tradingagents.dataflows import get_realtime_price
            price_info = await asyncio.get_event_loop().run_in_executor(
                None, get_realtime_price, ticker
            )
            prices[ticker] = price_info
        except Exception:
            pass
    return prices
```

### 1.6 性能考虑

| 优化项 | 方法 |
|--------|------|
| WebSocket 重连 | 断开后 5 秒自动重连，3 次失败后降级到轮询 |
| 轮询降级 | WebSocket 不可用时自动切换到 HTTP 轮询 |
| 请求合并 | 多个标的合并到一个请求中 |
| 节流 | 前端 300ms 节流更新，避免频繁 re-render |
| 内存 | 使用 `Map` 而非 `Record`，避免原型链污染 |

### 1.7 验收标准

- [ ] Watchlist 中的价格每 3-5 秒自动更新
- [ ] ChartHeader 价格实时跳动
- [ ] 涨跌颜色实时变化
- [ ] WebSocket 断开后自动重连
- [ ] WebSocket 不可用时降级到 HTTP 轮询
- [ ] 多个标的合并请求，不单独轮询

---

## 2. 自选股分组管理

### 2.1 背景

参考同花顺，自选股支持分组管理（如"科技股"、"消费股"、"观察中"）。

### 2.2 目标行为

```
▼ 科技股 (3)
  600733  12.34  +0.56  +4.76%
  AAPL    189.23 -1.23  -0.65%
  TSLA    245.67 +3.45  +1.43%

▼ 消费股 (2)
  600519  1680.00 +12.00 +0.72%
  000858  145.67  -2.34  -1.58%

▲ 观察中 (1)
  （折叠中，点击展开）
```

### 2.3 数据模型

```typescript
// types.ts
interface WatchlistGroup {
  id: string;
  name: string;
  collapsed: boolean;
  items: WatchlistItem[];
}

interface WatchlistItem {
  ticker: string;
  name?: string;
  lastPrice?: number;
  change?: number;
  changePercent?: number;
}

// localStorage key: "tradingagents_watchlist_groups"
```

### 2.4 UI 交互

| 操作 | 行为 |
|------|------|
| 点击分组名 | 展开/折叠 |
| 右键分组名 | 重命名 / 删除 / 新建分组 |
| 拖拽标的到分组 | 移动标的 |
| 点击标的 | 切换图表（已有） |
| 分组名旁 + | 新建分组 |

### 2.5 实现

#### 2.5.1 WatchlistPanel 重构

```typescript
// WatchlistPanel.tsx
const [groups, setGroups] = useState<WatchlistGroup[]>(() => loadGroups());
const [editingGroup, setEditingGroup] = useState<string | null>(null);

const toggleGroup = useCallback((groupId: string) => {
  setGroups(prev => prev.map(g =>
    g.id === groupId ? { ...g, collapsed: !g.collapsed } : g
  ));
}, []);

const renameGroup = useCallback((groupId: string, newName: string) => {
  setGroups(prev => prev.map(g =>
    g.id === groupId ? { ...g, name: newName } : g
  ));
}, []);

const createGroup = useCallback(() => {
  const newGroup: WatchlistGroup = {
    id: `group_${Date.now()}`,
    name: "新建分组",
    collapsed: false,
    items: [],
  };
  setGroups(prev => [...prev, newGroup]);
  setEditingGroup(newGroup.id);
}, []);

const deleteGroup = useCallback((groupId: string) => {
  setGroups(prev => prev.filter(g => g.id !== groupId));
}, []);

const moveToGroup = useCallback((ticker: string, fromGroupId: string, toGroupId: string) => {
  setGroups(prev => prev.map(g => {
    if (g.id === fromGroupId) {
      return { ...g, items: g.items.filter(i => i.ticker !== ticker) };
    }
    if (g.id === toGroupId) {
      const item = groups.find(grp => grp.id === fromGroupId)?.items.find(i => i.ticker === ticker);
      if (item && !g.items.some(i => i.ticker === ticker)) {
        return { ...g, items: [...g.items, item] };
      }
    }
    return g;
  }));
}, [groups]);
```

#### 2.5.2 localStorage 持久化

```typescript
const STORAGE_KEY = "tradingagents_watchlist_groups";

function loadGroups(): WatchlistGroup[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  // 默认分组
  return [{ id: "default", name: "自选股", collapsed: false, items: [] }];
}

function saveGroups(groups: WatchlistGroup[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(groups));
  } catch { /* ignore */ }
}
```

### 2.6 验收标准

- [ ] 自选股默认在一个分组中
- [ ] 可创建新分组
- [ ] 可重命名分组
- [ ] 可删除分组（标的移到默认分组）
- [ ] 可折叠/展开分组
- [ ] 分组状态持久化到 localStorage

---

## 3. 技术指标参数可调

### 3.1 目标行为

点击指标标签弹出参数设置弹窗：

```
┌─ MA 参数设置 ──────────────────┐
│  周期 1: [5  ]                 │
│  周期 2: [10 ]                 │
│  周期 3: [20 ]                 │
│  周期 4: [50 ]                 │
│                                │
│  [重置默认]          [确定]    │
└────────────────────────────────┘

┌─ MACD 参数设置 ────────────────┐
│  快线周期: [12]                │
│  慢线周期: [26]                │
│  信号线周期: [9]               │
│                                │
│  [重置默认]          [确定]    │
└────────────────────────────────┘

┌─ RSI 参数设置 ─────────────────┐
│  周期: [14]                    │
│  超买线: [70]                  │
│  超卖线: [30]                  │
│                                │
│  [重置默认]          [确定]    │
└────────────────────────────────┘
```

### 3.2 后端 API 扩展

```python
# schemas.py
class ChartDataRequest(BaseModel):
    ticker: str
    date: str
    days: int = 90
    # 新增可选参数
    ma_periods: list[int] | None = Field(default=None, description="MA 周期列表")
    macd_params: tuple[int, int, int] | None = Field(default=None, description="MACD (fast, slow, signal)")
    rsi_period: int | None = Field(default=None, description="RSI 周期")
```

### 3.3 前端参数状态

```typescript
// TradingViewLayout.tsx
const [indicatorParams, setIndicatorParams] = useState({
  ma_periods: [5, 10, 20, 50],
  macd_params: [12, 26, 9] as [number, number, number],
  rsi_period: 14,
  boll_period: 20,
  boll_std: 2,
});

// 切换时间周期时带上参数
const data = await api.getChartData(
  ticker, date, days, controller.signal, indicatorParams
);
```

### 3.4 验收标准

- [ ] 点击 MA 标签弹出参数设置弹窗
- [ ] 可修改 MA 周期（1-200）
- [ ] 修改后图表实时更新
- [ ] 可重置为默认参数
- [ ] 参数持久化到 localStorage

---

## 4. 文件变更汇总

| 文件 | 变更类型 | 功能 |
|------|---------|------|
| `lib/useRealtimePrices.ts` | 新建 | 实时价格 Hook |
| `lib/indicators.ts` | 新建 | WR/CCI 前端计算 |
| `lib/chart-utils.ts` | 修改 | 新增指标配置 |
| `components/tradingview/WatchlistPanel.tsx` | 重构 | 分组管理 + 实时价格 |
| `components/tradingview/ChartHeader.tsx` | 修改 | 价格跳动动画 |
| `components/tradingview/TradingViewLayout.tsx` | 修改 | 参数可调 + 实时价格 |
| `components/tradingview/types.ts` | 修改 | 新增 WatchlistGroup 类型 |
| `tradingagents_api/server.py` | 修改 | WebSocket + 实时价格端点 |
| `tradingagents_api/schemas.py` | 修改 | ChartDataRequest 扩展 |
| `tradingagents_api/chart_data.py` | 修改 | 支持自定义指标参数 |
