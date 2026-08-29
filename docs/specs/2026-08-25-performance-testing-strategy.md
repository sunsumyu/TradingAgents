# 性能优化 + 测试策略 + 代码质量

> 日期：2026-08-25

---

## 1. 性能优化

### 1.1 已实施优化

| 优化项 | 方法 | 效果 | 文件 |
|--------|------|------|------|
| mootdx 探测 | 8 秒全局截止 + max_probe=15 | 从 70s+ 降至 8s | `a_stock.py` |
| mootdx 调用 | 线程超时 8s | 单次挂起不再阻塞 | `a_stock.py` |
| 时间周期切换 | AbortController 取消旧请求 | 避免竞态过期数据 | `TradingViewLayout.tsx` |
| ECharts 渲染 | `animation: false` + `notMerge` | 减少不必要动画开销 | `TradingViewChart.tsx` |
| 请求合并 | A 股直接调用，绕过 vendor chain | 减少路由查找开销 | `chart_data.py` |

### 1.2 待实施优化

#### 1.2.1 图表数据虚拟化

**问题**：当数据集 >1000 bars 时，ECharts 渲染变慢。

**方案**：仅渲染可见区域的数据点。

```typescript
// TradingViewChart.tsx
const visibleData = useMemo(() => {
  if (!data || data.dates.length <= 500) return data;
  // 根据 dataZoom 的 start/end 过滤数据
  const startIdx = Math.floor(data.dates.length * zoomStart / 100);
  const endIdx = Math.ceil(data.dates.length * zoomEnd / 100);
  return {
    ...data,
    dates: data.dates.slice(startIdx, endIdx),
    ohlc: data.ohlc.slice(startIdx, endIdx),
    volumes: data.volumes.slice(startIdx, endIdx),
    // ... 其他字段
  };
}, [data, zoomStart, zoomEnd]);
```

**优先级**：P3（当前数据量通常 <500 bars，暂不需要）

#### 1.2.2 指标计算缓存

**问题**：相同参数的指标重复计算。

**方案**：使用 LRU 缓存。

```python
# chart_data.py
from functools import lru_cache

@lru_cache(maxsize=32)
def compute_ma(closes: tuple, period: int):
    # 计算移动平均线
    ...

# 注意：需要将 list 转为 tuple 才能缓存
closes_tuple = tuple(closes)
ma5 = compute_ma(closes_tuple, 5)
```

**优先级**：P3

#### 1.2.3 Watchlist 虚拟滚动

**问题**：自选股 >100 条时，DOM 节点过多。

**方案**：使用 `react-window` 虚拟列表。

```typescript
import { FixedSizeList } from "react-window";

<FixedSizeList
  height={containerHeight}
  itemCount={items.length}
  itemSize={32}
  width="100%"
>
  {({ index, style }) => (
    <div style={style}>
      <WatchlistItemRow item={items[index]} />
    </div>
  )}
</FixedSizeList>
```

**优先级**：P4（普通用户自选股 <50 条）

#### 1.2.4 ECharts 实例复用

**问题**：频繁切换时间周期时，ECharts 实例被销毁重建。

**方案**：使用 `notMerge={false}` + `setOption` 更新。

```typescript
// TradingViewChart.tsx
// 当前：notMerge={true}（每次全量替换）
// 优化：notMerge={false}（增量更新）
<ReactECharts
  option={option}
  notMerge={false}  // 改为增量更新
  lazyUpdate={true}  // 延迟更新
/>
```

**注意**：需要确保 option 结构变化时正确合并。

**优先级**：P3

---

## 2. 测试策略

### 2.1 已有测试

| 文件 | 测试内容 | 运行方式 |
|------|---------|---------|
| `tests/test_astock_review_fixes.py` | A 股数据获取修复验证 | `pytest tests/test_astock_review_fixes.py` |
| `tests/test_multi_platform_llm.py` | 多平台 LLM 配置验证 | `pytest tests/test_multi_platform_llm.py` |
| `tests/test_progress_callback.py` | 进度回调机制验证 | `pytest tests/test_progress_callback.py` |

### 2.2 后端单元测试

#### 2.2.1 CSV 解析器测试

```python
# tests/test_csv_parser.py
import pytest
from tradingagents_api.chart_data import parse_ohlcv_csv

def test_parse_6_column_csv():
    """a_stock 返回的 6 列 CSV"""
    csv_text = """Date,Open,High,Low,Close,Volume
2026-01-01,10.00,10.50,9.80,10.20,123456
2026-01-02,10.20,10.80,10.10,10.60,234567"""
    records = parse_ohlcv_csv(csv_text)
    assert len(records) == 2
    assert records[0]["open"] == 10.00
    assert records[0]["close"] == 10.20
    assert records[0]["volume"] == 123456

def test_parse_7_column_csv():
    """yfinance 返回的 7 列 CSV"""
    csv_text = """Date,Open,High,Low,Close,Adj Close,Volume
2026-01-01,10.00,10.50,9.80,10.20,10.15,123456"""
    records = parse_ohlcv_csv(csv_text)
    assert len(records) == 1
    assert records[0]["adj_close"] == 10.15

def test_parse_empty_csv():
    records = parse_ohlcv_csv("")
    assert records == []

def test_parse_invalid_csv():
    records = parse_ohlcv_csv("not,a,csv")
    assert records == []
```

#### 2.2.2 A 股标的识别测试

```python
# tests/test_astock_symbol.py
import pytest
from tradingagents_api.chart_data import _is_astock_symbol

def test_6_digit_code():
    assert _is_astock_symbol("600733") is True
    assert _is_astock_symbol("000001") is True
    assert _is_astock_symbol("300001") is True

def test_with_suffix():
    assert _is_astock_symbol("600733.SH") is True
    assert _is_astock_symbol("600733.SZ") is True

def test_us_stock():
    assert _is_astock_symbol("AAPL") is False
    assert _is_astock_symbol("TSLA") is False

def test_hk_stock():
    assert _is_astock_symbol("0700.HK") is False

def test_crypto():
    assert _is_astock_symbol("BTC-USD") is False
```

#### 2.2.3 指标计算测试

```python
# tests/test_indicators.py
import pytest
import numpy as np
from tradingagents_api.chart_data import compute_ma, compute_rsi, compute_macd

def test_compute_ma():
    closes = [10, 11, 12, 13, 14, 15]
    ma3 = compute_ma(closes, 3)
    assert ma3[:2] == [None, None]  # 前 2 个无值
    assert ma3[2] == pytest.approx(11.0)  # (10+11+12)/3
    assert ma3[5] == pytest.approx(14.0)  # (13+14+15)/3

def test_compute_rsi():
    # RSI 计算验证
    closes = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84]
    rsi = compute_rsi(closes, period=3)
    assert all(0 <= v <= 100 for v in rsi if v is not None)

def test_compute_macd():
    # MACD 计算验证
    closes = list(range(30, 60))  # 30 天数据
    macd_line, signal_line, histogram = compute_macd(closes)
    assert len(macd_line) == len(closes)
    assert len(signal_line) == len(closes)
    assert len(histogram) == len(closes)
    # histogram = macd - signal
    for i in range(len(closes)):
        if histogram[i] is not None:
            assert histogram[i] == pytest.approx(macd_line[i] - signal_line[i], abs=1e-10)
```

### 2.3 后端集成测试

```python
# tests/test_chart_data_api.py
import pytest
import httpx

BASE_URL = "http://127.0.0.1:8420"

@pytest.mark.integration
async def test_chart_data_us_stock():
    """测试美股图表数据"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/api/chart-data", json={
            "ticker": "AAPL",
            "date": "2026-08-25",
            "days": 90,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "kline" in data
        assert data["kline"]["dates"]  # 非空
        assert len(data["kline"]["ohlc"]) > 0

@pytest.mark.integration
async def test_chart_data_astock():
    """测试 A 股图表数据"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/api/chart-data", json={
            "ticker": "600733",
            "date": "2026-08-25",
            "days": 90,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "kline" in data
        assert len(data["kline"]["ohlc"]) > 0

@pytest.mark.integration
async def test_chart_data_invalid_ticker():
    """测试无效标的"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/api/chart-data", json={
            "ticker": "INVALID_TICKER_XYZ",
            "date": "2026-08-25",
            "days": 90,
        })
        # 应返回错误或空数据
        assert resp.status_code in [200, 400, 404]
```

### 2.4 前端 E2E 测试（Playwright）

```typescript
// tests/e2e/chart.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Chart functionality", () => {
  test("timeframe switching", async ({ page }) => {
    await page.goto("http://localhost:5173");
    // 等待图表加载
    await page.waitForSelector("[data-testid='trading-view-chart']");

    // 点击 1W 周期
    await page.click("button:has-text('1W')");
    await page.waitForSelector("[data-testid='loading-overlay']");

    // 等待加载完成
    await page.waitForSelector("[data-testid='loading-overlay']", { state: "hidden" });

    // 验证图表已更新
    const chart = await page.$("[data-testid='trading-view-chart']");
    expect(chart).toBeTruthy();
  });

  test("watchlist click switches ticker", async ({ page }) => {
    await page.goto("http://localhost:5173");

    // 等待 Watchlist 加载
    await page.waitForSelector("[data-testid='watchlist-panel']");

    // 点击第一个自选股
    const firstItem = await page.$("[data-testid='watchlist-item']:first-child");
    await firstItem?.click();

    // 验证 ChartHeader 更新
    const header = await page.textContent("[data-testid='chart-header']");
    expect(header).toContain("600733"); // 或其他标的
  });

  test("drawing tool works", async ({ page }) => {
    await page.goto("http://localhost:5173");
    await page.waitForSelector("[data-testid='trading-view-chart']");

    // 选择趋势线工具
    await page.click("[data-testid='drawing-tool-trendline']");

    // 在图表上绘制
    const chart = await page.$("[data-testid='trading-view-chart']");
    const box = await chart?.boundingBox();
    if (box) {
      await page.mouse.move(box.x + 100, box.y + 100);
      await page.mouse.down();
      await page.mouse.move(box.x + 300, box.y + 200);
      await page.mouse.up();
    }

    // 验证绘图存在
    const canvas = await page.$("canvas[data-testid='drawing-canvas']");
    expect(canvas).toBeTruthy();
  });
});
```

---

## 3. 代码质量

### 3.1 ESLint 规则

```json
// .eslintrc.json
{
  "extends": ["react-app", "react-app/jest"],
  "rules": {
    "no-unused-vars": "warn",
    "no-console": ["warn", { "allow": ["error", "warn"] }],
    "prefer-const": "error",
    "react-hooks/exhaustive-deps": "warn",
    "@typescript-eslint/no-explicit-any": "warn"
  }
}
```

### 3.2 Prettier 配置

```json
// .prettierrc
{
  "semi": true,
  "singleQuote": false,
  "tabWidth": 2,
  "trailingComma": "all",
  "printWidth": 100
}
```

### 3.3 Git Hooks（pre-commit）

```bash
# .husky/pre-commit
#!/bin/sh
npx lint-staged

# lint-staged config
# package.json
"lint-staged": {
  "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
  "*.{json,md}": ["prettier --write"]
}
```

### 3.4 代码审查清单

- [ ] 所有新增组件都有 TypeScript 类型定义
- [ ] 事件处理函数使用 `useCallback` 避免不必要的 re-render
- [ ] 大型对象使用 `useMemo` 缓存
- [ ] API 调用都有错误处理和 loading 状态
- [ ] 组件 Props 都有 JSDoc 注释
- [ ] 新增文件都有文件头注释
- [ ] 没有 `any` 类型（或有 `@ts-ignore` + 原因说明）
- [ ] 没有 console.log（只有 console.error/warn）
- [ ] CSS 使用 Tailwind 类名（避免内联样式，除非动态值）
- [ ] 所有 API 端点都有 OpenAPI 文档（FastAPI 自动）

---

## 4. CI/CD 建议

### 4.1 GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[test]"
      - run: pytest tests/ -v

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: cd tradingagents_gui && npm ci
      - run: npm run lint
      - run: npm run build

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: cd tradingagents_gui && npm ci
      - run: npx tsc --noEmit
```

### 4.2 版本发布

```bash
# Bump version
npm version patch  # 0.1.0 → 0.1.1
# 或
npm version minor  # 0.1.0 → 0.2.0

# Build
cd tradingagents_gui && npm run tauri build

# 产物位置
tradingagents_gui/target/release/bundle/
├── nsis/           # Windows 安装包
├── dmg/            # macOS 安装包
└── AppImage/       # Linux 安装包
```

---

## 5. 文档维护

### 5.1 文档结构

```
docs/
├── specs/
│   ├── 2026-08-25-tradingview-quality-gui-master-plan.md    # 主规划文档
│   ├── 2026-08-25-phase3-indicator-bar.md                   # 指标参数栏规格
│   ├── 2026-08-25-phase3-kdj-crosshair-screenshot.md        # KDJ+光标+截图规格
│   ├── 2026-08-25-phase3-drawing-undo-subpanel-switch.md    # 绘图撤销+副图切换规格
│   ├── 2026-08-25-phase4-realtime-watchlist-api-design.md   # 实时价格+分组+API设计
│   └── 2026-08-25-performance-testing-strategy.md           # 本文档
├── GUI_README.md                                             # GUI 使用说明
└── PROJECT_ANALYSIS.md                                       # 项目分析
```

### 5.2 文档更新规则

1. 每次功能完成后，更新 master-plan.md 中的状态（✅ → ✅）
2. 新功能先写规格文档，再写代码
3. 代码变更后更新文件变更清单
4. 每月审查一次性能优化清单
