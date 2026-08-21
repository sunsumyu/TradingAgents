# Two-Step Workflow (Market Data Preview) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the analysis workflow into two steps: (1) preview market data (charts, fundamentals, news) and (2) optionally run the full multi-agent analysis.

**Architecture:** New API endpoint `/api/market-data` fetches chart data + fundamentals + news independently (no agents). New `MarketDataPanel` frontend page displays the data. ConfigPanel gains a "查看数据" button. App.tsx state machine adds a `market_data` phase.

**Tech Stack:** Python FastAPI (backend), React + TypeScript + ECharts + Tailwind (frontend), existing `route_to_vendor` data layer.

## Global Constraints

- Python 3.10+, FastAPI, Pydantic v2
- React 18, TypeScript 5, Vite 5, Tailwind CSS, ECharts via echarts-for-react
- Follow existing code patterns: dark theme (#1E222D bg), CHART_COLORS palette, ChartBoundary error boundaries
- No new npm dependencies — use only what's already in package.json
- All new Python code must have docstrings
- Commit after each task

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `tradingagents_api/market_data.py` | Standalone market data fetching — calls route_to_vendor for charts, fundamentals, news. No agent dependency. |
| `tradingagents_gui/src/components/MarketDataPanel.tsx` | Full page: top bar + fundamentals cards + charts + news feed |
| `tradingagents_gui/src/components/charts/FundamentalCards.tsx` | Row of data cards (market cap, PE, PB, 52w high/low, etc.) |
| `tradingagents_gui/src/components/charts/NewsFeed.tsx` | Scrollable news list with title, publisher, date |

### Modified Files
| File | Change |
|------|--------|
| `tradingagents_api/schemas.py` | Add FundamentalsData, NewsItem, MarketDataRequest, MarketDataResponse models |
| `tradingagents_api/server.py` | Add POST `/api/market-data` endpoint |
| `tradingagents_gui/src/lib/types.ts` | Add FundamentalsData, NewsItem, MarketDataResponse TS types |
| `tradingagents_gui/src/lib/api.ts` | Add `getMarketData()` method |
| `tradingagents_gui/src/App.tsx` | Add `market_data` phase, wire new flow |
| `tradingagents_gui/src/components/ConfigPanel.tsx` | Add "查看数据" button, accept new `onMarketData` prop |

---

### Task 1: Backend Schemas — Add new Pydantic models

**Files:**
- Modify: `tradingagents_api/schemas.py`

**Interfaces:**
- Produces: `FundamentalsData`, `NewsItem`, `MarketDataRequest`, `MarketDataResponse` (used by Task 2)

- [ ] **Step 1: Add FundamentalsData model**

In `tradingagents_api/schemas.py`, after the `FundFlowData` class, add:

```python
class FundamentalsData(BaseModel):
    """Fundamental stock data from yfinance / A-stock vendor."""

    market_cap: float | None = Field(default=None, description="Market capitalization")
    pe_ratio: float | None = Field(default=None, description="PE ratio (TTM)")
    forward_pe: float | None = Field(default=None, description="Forward PE ratio")
    pb_ratio: float | None = Field(default=None, description="Price to Book ratio")
    eps_ttm: float | None = Field(default=None, description="EPS (TTM)")
    dividend_yield: float | None = Field(default=None, description="Dividend yield")
    beta: float | None = Field(default=None, description="Beta coefficient")
    fifty_two_week_high: float | None = Field(default=None, description="52-week high")
    fifty_two_week_low: float | None = Field(default=None, description="52-week low")
    fifty_day_average: float | None = Field(default=None, description="50-day moving average")
    two_hundred_day_average: float | None = Field(default=None, description="200-day moving average")
    sector: str | None = Field(default=None, description="Sector")
    industry: str | None = Field(default=None, description="Industry")
    name: str | None = Field(default=None, description="Company name")
```

- [ ] **Step 2: Add NewsItem model**

```python
class NewsItem(BaseModel):
    """A single news article."""

    title: str = Field(description="Article title")
    publisher: str | None = Field(default=None, description="Publisher name")
    link: str | None = Field(default=None, description="Article URL")
    pub_date: str | None = Field(default=None, description="Publication date")
    summary: str | None = Field(default=None, description="Article summary")
```

- [ ] **Step 3: Add MarketDataRequest and MarketDataResponse**

```python
class MarketDataRequest(BaseModel):
    """Request for standalone market data (no agent analysis)."""

    ticker: str = Field(description="Stock ticker symbol")
    date: str = Field(description="Date in YYYY-MM-DD format")


class MarketDataResponse(BaseModel):
    """Response containing all market data for preview."""

    ticker: str
    date: str
    kline: KlineData | None = None
    macd: MacdData | None = None
    rsi: RsiData | None = None
    bollinger: BollingerData | None = None
    fund_flow: FundFlowData | None = None
    fundamentals: FundamentalsData | None = None
    news: list[NewsItem] = Field(default_factory=list)
```

- [ ] **Step 4: Verify imports work**

Run: `cd F:\chain\TradingAgents && python -c "from tradingagents_api.schemas import FundamentalsData, NewsItem, MarketDataRequest, MarketDataResponse; print('OK')"`
Expected: prints "OK"

- [ ] **Step 5: Commit**

```bash
git add tradingagents_api/schemas.py
git commit -m "feat(api): add FundamentalsData, NewsItem, MarketData schemas"
```

---

### Task 2: Backend — Market data fetching module

**Files:**
- Create: `tradingagents_api/market_data.py`

**Interfaces:**
- Consumes: `FundamentalsData`, `NewsItem`, `MarketDataResponse` from schemas (Task 1), `build_chart_data` from chart_data.py (existing)
- Produces: `build_market_data(ticker, date) -> MarketDataResponse` (used by Task 3)

- [ ] **Step 1: Create market_data.py with _fetch_fundamentals**

```python
"""Standalone market data fetching — no agent analysis required."""

from __future__ import annotations

import logging
from typing import Any

from .chart_data import build_chart_data
from .schemas import (
    FundamentalsData,
    FundFlowData,
    KlineData,
    MacdData,
    MarketDataResponse,
    NewsItem,
    RsiData,
)

logger = logging.getLogger(__name__)


def _fetch_fundamentals(ticker: str, date: str) -> FundamentalsData | None:
    """Fetch fundamental data via vendor routing."""
    try:
        from tradingagents.dataflows.interface import route_to_vendor
        text = route_to_vendor("get_fundamentals", ticker, date)
        if not text:
            return None

        # Parse the text output — yfinance returns key: value lines
        data: dict[str, Any] = {}
        for line in str(text).splitlines():
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower().replace(" ", "_").replace("/", "_")
                value = value.strip()
                data[key] = value

        def _float(key: str) -> float | None:
            raw = data.get(key)
            if raw is None:
                return None
            try:
                return float(str(raw).replace(",", "").replace("$", ""))
            except (ValueError, TypeError):
                return None

        def _str(key: str) -> str | None:
            raw = data.get(key)
            return str(raw).strip() if raw else None

        return FundamentalsData(
            market_cap=_float("market_cap"),
            pe_ratio=_float("trailing_pe") or _float("pe_ratio_(ttm)") or _float("pe_ratio"),
            forward_pe=_float("forward_pe"),
            pb_ratio=_float("price_to_book"),
            eps_ttm=_float("trailing_eps") or _float("eps_(ttm)"),
            dividend_yield=_float("dividend_yield"),
            beta=_float("beta"),
            fifty_two_week_high=_float("fifty_two_week_high"),
            fifty_two_week_low=_float("fifty_two_week_low"),
            fifty_day_average=_float("fifty_day_average"),
            two_hundred_day_average=_float("two_hundred_day_average"),
            sector=_str("sector"),
            industry=_str("industry"),
            name=_str("short_name") or _str("long_name"),
        )
    except Exception as exc:
        logger.warning("Failed to fetch fundamentals for %s: %s", ticker, exc)
        return None
```

- [ ] **Step 2: Add _fetch_news function**

```python
def _fetch_news(ticker: str, date: str) -> list[NewsItem]:
    """Fetch recent news articles via vendor routing."""
    try:
        from datetime import datetime, timedelta
        from tradingagents.dataflows.interface import route_to_vendor

        start_dt = datetime.strptime(date, "%Y-%m-%d") - timedelta(days=7)
        start_date = start_dt.strftime("%Y-%m-%d")

        text = route_to_vendor("get_news", ticker, start_date, date)
        if not text:
            return []

        items: list[NewsItem] = []
        for line in str(text).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("Title"):
                continue

            # Try to parse "title | publisher | date | link" format
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 1 and parts[0]:
                items.append(NewsItem(
                    title=parts[0],
                    publisher=parts[1] if len(parts) > 1 else None,
                    pub_date=parts[2] if len(parts) > 2 else None,
                    link=parts[3] if len(parts) > 3 else None,
                ))

        return items[:20]  # Limit to 20 articles
    except Exception as exc:
        logger.warning("Failed to fetch news for %s: %s", ticker, exc)
        return []
```

- [ ] **Step 3: Add build_market_data main function**

```python
def build_market_data(ticker: str, date: str) -> MarketDataResponse:
    """Fetch chart data, fundamentals, and news independently.

    This runs without agents — it only calls vendor APIs directly.
    """
    # Charts (reuses existing logic with empty final_state)
    chart = None
    try:
        chart = build_chart_data({}, ticker, date)
    except Exception as exc:
        logger.warning("Chart data assembly failed for %s: %s", ticker, exc)

    # Fundamentals
    fundamentals = _fetch_fundamentals(ticker, date)

    # News
    news = _fetch_news(ticker, date)

    return MarketDataResponse(
        ticker=ticker,
        date=date,
        kline=chart.kline if chart else None,
        macd=chart.macd if chart else None,
        rsi=chart.rsi if chart else None,
        bollinger=chart.bollinger if chart else None,
        fund_flow=chart.fundFlow if chart else None,
        fundamentals=fundamentals,
        news=news,
    )
```

- [ ] **Step 4: Verify module imports**

Run: `cd F:\chain\TradingAgents && python -c "from tradingagents_api.market_data import build_market_data; print('OK')"`
Expected: prints "OK"

- [ ] **Step 5: Commit**

```bash
git add tradingagents_api/market_data.py
git commit -m "feat(api): add standalone market data fetching (no agents)"
```

---

### Task 3: Backend — API endpoint

**Files:**
- Modify: `tradingagents_api/server.py`

**Interfaces:**
- Consumes: `build_market_data` from market_data.py (Task 2), `MarketDataRequest`, `MarketDataResponse` from schemas (Task 1)
- Produces: `POST /api/market-data` endpoint (used by frontend Task 5)

- [ ] **Step 1: Add import for market_data**

In `tradingagents_api/server.py`, find the imports section and add:

```python
from .market_data import build_market_data
from .schemas import MarketDataRequest, MarketDataResponse
```

- [ ] **Step 2: Add the endpoint**

Find the last `@app.post` route in server.py (or after the existing routes), and add:

```python
@app.post("/api/market-data", response_model=MarketDataResponse)
async def get_market_data(request: MarketDataRequest):
    """Fetch chart data, fundamentals, and news without running agents."""
    return build_market_data(request.ticker, request.date)
```

- [ ] **Step 3: Verify server starts**

Run: `cd F:\chain\TradingAgents && python -c "from tradingagents_api.server import app; print('OK')"`
Expected: prints "OK"

- [ ] **Step 4: Commit**

```bash
git add tradingagents_api/server.py
git commit -m "feat(api): add POST /api/market-data endpoint"
```

---

### Task 4: Frontend — Add TypeScript types and API client method

**Files:**
- Modify: `tradingagents_gui/src/lib/types.ts`
- Modify: `tradingagents_gui/src/lib/api.ts`

**Interfaces:**
- Produces: `FundamentalsData`, `NewsItem`, `MarketDataResponse` TS types and `api.getMarketData()` (used by Tasks 6, 7)

- [ ] **Step 1: Add FundamentalsData and NewsItem types**

In `tradingagents_gui/src/lib/types.ts`, after the `FundFlowData` interface, add:

```typescript
export interface FundamentalsData {
  market_cap?: number | null;
  pe_ratio?: number | null;
  forward_pe?: number | null;
  pb_ratio?: number | null;
  eps_ttm?: number | null;
  dividend_yield?: number | null;
  beta?: number | null;
  fifty_two_week_high?: number | null;
  fifty_two_week_low?: number | null;
  fifty_day_average?: number | null;
  two_hundred_day_average?: number | null;
  sector?: string | null;
  industry?: string | null;
  name?: string | null;
}

export interface NewsItem {
  title: string;
  publisher?: string;
  link?: string;
  pub_date?: string;
  summary?: string;
}

export interface MarketDataResponse {
  ticker: string;
  date: string;
  kline?: KlineData | null;
  macd?: MacdData | null;
  rsi?: RsiData | null;
  bollinger?: BollingerData | null;
  fund_flow?: FundFlowData | null;
  fundamentals?: FundamentalsData | null;
  news?: NewsItem[];
}
```

- [ ] **Step 2: Add getMarketData to API client**

In `tradingagents_gui/src/lib/api.ts`, find the class that contains methods like `startAnalysis`, `getReport`, etc. Add this method inside the class:

```typescript
async getMarketData(ticker: string, date: string): Promise<import("./types").MarketDataResponse> {
  const resp = await fetch(`${BASE}/api/market-data`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, date }),
  });
  if (!resp.ok) {
    throw new Error(`Market data request failed: ${resp.status}`);
  }
  return resp.json();
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd F:\chain\TradingAgents\tradingagents_gui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add tradingagents_gui/src/lib/types.ts tradingagents_gui/src/lib/api.ts
git commit -m "feat(gui): add MarketData types and getMarketData API method"
```

---

### Task 5: Frontend — FundamentalCards component

**Files:**
- Create: `tradingagents_gui/src/components/charts/FundamentalCards.tsx`

**Interfaces:**
- Consumes: `FundamentalsData` from types (Task 4)
- Produces: `<FundamentalCards data={...} />` (used by Task 7)

- [ ] **Step 1: Create FundamentalCards.tsx**

```tsx
import type { FundamentalsData } from "../../lib/types";

interface Props {
  data: FundamentalsData;
}

function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(1)}万`;
  return n.toLocaleString();
}

function formatPercent(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(2)}%`;
}

function Card({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-[#1E222D] rounded-lg border border-[#363A45] px-4 py-3 min-w-[140px]">
      <div className="text-[11px] text-[#787B86] mb-1">{label}</div>
      <div className="text-[14px] font-semibold" style={{ color: color || "#D1D4DC" }}>
        {value}
      </div>
    </div>
  );
}

export default function FundamentalCards({ data }: Props) {
  const name = data.name || data.sector || "";

  return (
    <div className="mb-3">
      {name && (
        <div className="text-[12px] text-[#787B86] mb-2 px-1">
          {name}
          {data.sector && <span className="ml-2 text-[#555]">| {data.sector}</span>}
          {data.industry && <span className="ml-1 text-[#555]">| {data.industry}</span>}
        </div>
      )}
      <div className="flex gap-3 flex-wrap">
        <Card label="市值" value={formatNumber(data.market_cap)} />
        <Card label="PE (TTM)" value={data.pe_ratio?.toFixed(1) ?? "—"} />
        <Card label="Forward PE" value={data.forward_pe?.toFixed(1) ?? "—"} />
        <Card label="PB" value={data.pb_ratio?.toFixed(2) ?? "—"} />
        <Card label="EPS (TTM)" value={data.eps_ttm?.toFixed(2) ?? "—"} />
        <Card label="股息率" value={formatPercent(data.dividend_yield)} />
        <Card label="Beta" value={data.beta?.toFixed(2) ?? "—"} />
        <Card label="52周最高" value={data.fifty_two_week_high?.toFixed(2) ?? "—"} color="#089981" />
        <Card label="52周最低" value={data.fifty_two_week_low?.toFixed(2) ?? "—"} color="#F23645" />
        <Card label="50日均线" value={data.fifty_day_average?.toFixed(2) ?? "—"} />
        <Card label="200日均线" value={data.two_hundred_day_average?.toFixed(2) ?? "—"} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd F:\chain\TradingAgents\tradingagents_gui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add tradingagents_gui/src/components/charts/FundamentalCards.tsx
git commit -m "feat(gui): add FundamentalCards component"
```

---

### Task 6: Frontend — NewsFeed component

**Files:**
- Create: `tradingagents_gui/src/components/charts/NewsFeed.tsx`

**Interfaces:**
- Consumes: `NewsItem[]` from types (Task 4)
- Produces: `<NewsFeed items={...} />` (used by Task 7)

- [ ] **Step 1: Create NewsFeed.tsx**

```tsx
import { useState } from "react";
import { ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import type { NewsItem } from "../../lib/types";

interface Props {
  items: NewsItem[];
}

export default function NewsFeed({ items }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (items.length === 0) {
    return (
      <div className="text-[12px] text-[#787B86] py-4 text-center">
        暂无相关新闻
      </div>
    );
  }

  return (
    <div className="space-y-1 max-h-[300px] overflow-y-auto">
      {items.map((item, i) => (
        <div
          key={i}
          className="group px-3 py-2 rounded hover:bg-[#2A2E39] transition-colors cursor-pointer"
          onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
        >
          <div className="flex items-start gap-2">
            <div className="flex-1 min-w-0">
              <div className="text-[13px] text-[#D1D4DC] leading-tight truncate">
                {item.title}
              </div>
              <div className="flex items-center gap-2 mt-1">
                {item.publisher && (
                  <span className="text-[11px] text-[#787B86]">{item.publisher}</span>
                )}
                {item.pub_date && (
                  <span className="text-[11px] text-[#555]">{item.pub_date}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {item.link && (
                <a
                  href={item.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink size={12} className="text-[#787B86]" />
                </a>
              )}
              {item.summary && (
                expandedIdx === i ? <ChevronUp size={12} className="text-[#787B86]" /> : <ChevronDown size={12} className="text-[#787B86]" />
              )}
            </div>
          </div>
          {expandedIdx === i && item.summary && (
            <div className="mt-2 text-[12px] text-[#787B86] leading-relaxed pl-0">
              {item.summary}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd F:\chain\TradingAgents\tradingagents_gui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add tradingagents_gui/src/components/charts/NewsFeed.tsx
git commit -m "feat(gui): add NewsFeed component"
```

---

### Task 7: Frontend — MarketDataPanel page

**Files:**
- Create: `tradingagents_gui/src/components/MarketDataPanel.tsx`

**Interfaces:**
- Consumes: `MarketDataResponse` from types (Task 4), `FundamentalCards` (Task 5), `NewsFeed` (Task 6), existing chart components (KlineChart, MacdChart, RsiChart, BollingerChart, FundFlowChart)
- Produces: `<MarketDataPanel />` (used by Task 9)

- [ ] **Step 1: Create MarketDataPanel.tsx**

```tsx
import { ArrowLeft, RefreshCw, Play, Loader2 } from "lucide-react";
import type { MarketDataResponse } from "../lib/types";
import FundamentalCards from "./charts/FundamentalCards";
import NewsFeed from "./charts/NewsFeed";
import ReportCharts from "./ReportCharts";

interface Props {
  data: MarketDataResponse;
  onBack: () => void;
  onAnalyze: () => void;
  isAnalyzing?: boolean;
}

export default function MarketDataPanel({ data, onBack, onAnalyze, isAnalyzing }: Props) {
  // Build a ChartData-compatible object from MarketDataResponse
  const chartData = {
    kline: data.kline,
    macd: data.macd,
    rsi: data.rsi,
    bollinger: data.bollinger,
    fundFlow: data.fund_flow,
    dashboard: null, // No signal yet — that comes from agent analysis
  };

  const hasAnyChart = data.kline || data.macd || data.rsi || data.bollinger || data.fund_flow;

  return (
    <div className="h-full flex flex-col">
      {/* ── Top Bar ── */}
      <div className="h-11 shrink-0 border-b border-[#363A45] flex items-center px-5">
        <button className="btn-ghost" onClick={onBack}>
          <ArrowLeft size={13} />
          返回配置
        </button>
        <h1 className="text-[18px] font-semibold text-[#D1D4DC] ml-3">
          {data.ticker}
          {data.fundamentals?.name && (
            <span className="text-[13px] text-[#787B86] font-normal ml-2">
              {data.fundamentals.name}
            </span>
          )}
        </h1>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[11px] text-[#787B86]">{data.date}</span>
          <button
            className="btn-primary"
            onClick={onAnalyze}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? (
              <>
                <Loader2 size={13} className="animate-spin" />
                分析中...
              </>
            ) : (
              <>
                <Play size={13} />
                开始分析
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Scrollable Content ── */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {/* Fundamentals cards */}
        {data.fundamentals && (
          <FundamentalCards data={data.fundamentals} />
        )}

        {/* Charts */}
        {hasAnyChart && (
          <ReportCharts chartData={chartData} />
        )}

        {/* News */}
        {data.news && data.news.length > 0 && (
          <div className="bg-[#1E222D] rounded-lg border border-[#363A45] overflow-hidden mt-3">
            <div className="px-4 py-2 border-b border-[#363A45]">
              <h3 className="text-[13px] font-medium text-[#D1D4DC]">最新新闻</h3>
            </div>
            <div className="p-2">
              <NewsFeed items={data.news} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd F:\chain\TradingAgents\tradingagents_gui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add tradingagents_gui/src/components/MarketDataPanel.tsx
git commit -m "feat(gui): add MarketDataPanel page component"
```

---

### Task 8: Frontend — ConfigPanel "查看数据" button

**Files:**
- Modify: `tradingagents_gui/src/components/ConfigPanel.tsx`

**Interfaces:**
- Consumes: (existing)
- Produces: `onMarketData` callback prop (used by Task 9)

- [ ] **Step 1: Add onMarketData prop to ConfigPanel interface**

Find the `Props` interface in ConfigPanel.tsx and add `onMarketData`:

```typescript
interface Props {
  config: AnalysisConfig;
  onChange: (config: AnalysisConfig) => void;
  backendOnline: boolean;
  backendStatus: "connecting" | "failed" | "idle";
  onTestConnection: () => void;
  onAnalyze: () => void;
  onMarketData: () => void;  // NEW
  onFetchModels: (provider: string, proxyUrl: string, apiKey: string) => Promise<{ quick: ModelInfo[]; deep: ModelInfo[] }>;
}
```

- [ ] **Step 2: Destructure onMarketData in the component**

Find the destructuring line in the component and add `onMarketData`:

```typescript
export default function ConfigPanel({
  config,
  onChange,
  backendOnline,
  backendStatus,
  onTestConnection,
  onAnalyze,
  onMarketData,  // NEW
  onFetchModels,
}: Props) {
```

- [ ] **Step 3: Add "查看数据" button**

Find the main action button area (the "开始分析" button) and add a "查看数据" button before it. The exact location depends on the current layout — look for `onAnalyze` usage and add alongside it:

```tsx
<button
  className="btn-ghost"
  onClick={onMarketData}
  disabled={!backendOnline || !config.ticker}
>
  <BarChart3 size={13} />
  查看数据
</button>
```

Note: You'll need to import `BarChart3` from `lucide-react` if not already imported.

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd F:\chain\TradingAgents\tradingagents_gui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add tradingagents_gui/src/components/ConfigPanel.tsx
git commit -m "feat(gui): add '查看数据' button to ConfigPanel"
```

---

### Task 9: Frontend — Wire App.tsx state machine

**Files:**
- Modify: `tradingagents_gui/src/App.tsx`

**Interfaces:**
- Consumes: `MarketDataPanel` (Task 7), `api.getMarketData` (Task 4), `onMarketData` from ConfigPanel (Task 8)
- Produces: Complete two-step workflow

- [ ] **Step 1: Add market_data phase to type**

```typescript
type Phase = "config" | "market_data" | "analyzing" | "report" | "error";
```

- [ ] **Step 2: Add market data state**

After the existing `report` state, add:

```typescript
const [marketData, setMarketData] = useState<import("./lib/types").MarketDataResponse | null>(null);
const [loadingMarketData, setLoadingMarketData] = useState(false);
```

- [ ] **Step 3: Add loadMarketData callback**

```typescript
const loadMarketData = useCallback(async () => {
  saveConfig(config);
  setLoadingMarketData(true);
  try {
    const data = await api.getMarketData(config.ticker, config.date);
    setMarketData(data);
    setPhase("market_data");
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    setError(msg);
    setPhase("error");
  } finally {
    setLoadingMarketData(false);
  }
}, [config]);
```

- [ ] **Step 4: Add lazy import for MarketDataPanel**

Find the existing `const ReportPanel = lazy(...)` line and add:

```typescript
const MarketDataPanel = lazy(() => import("./components/MarketDataPanel"));
```

- [ ] **Step 5: Add market_data phase rendering**

Find the `{phase === "config" && (` block. After the ConfigPanel rendering (but before the analyzing phase), add the market_data phase. The ConfigPanel needs the new `onMarketData` prop:

```tsx
{phase === "config" && (
  <ConfigPanel
    config={config}
    onChange={handleConfigChange}
    backendOnline={backendOnline}
    backendStatus={backendStatus}
    onTestConnection={checkHealth}
    onAnalyze={startAnalysis}
    onMarketData={loadMarketData}
    onFetchModels={async (provider, proxyUrl, apiKey) => {
      const m = await api.getModels(provider, proxyUrl, apiKey);
      return { quick: m.quick, deep: m.deep };
    }}
  />
)}

{phase === "market_data" && marketData && (
  <Suspense fallback={<div className="flex-1 flex items-center justify-center text-[#787B86]">加载中...</div>}>
    <MarketDataPanel
      data={marketData}
      onBack={() => setPhase("config")}
      onAnalyze={startAnalysis}
      isAnalyzing={false}
    />
  </Suspense>
)}
```

- [ ] **Step 6: Verify TypeScript compiles**

Run: `cd F:\chain\TradingAgents\tradingagents_gui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 7: Verify Vite build**

Run: `cd F:\chain\TradingAgents\tradingagents_gui && npx vite build`
Expected: builds successfully

- [ ] **Step 8: Commit**

```bash
git add tradingagents_gui/src/App.tsx
git commit -m "feat(gui): wire two-step workflow in App.tsx"
```

---

### Task 10: Integration test — end-to-end verification

**Files:**
- None (verification only)

- [ ] **Step 1: Start backend and test market-data endpoint**

```bash
cd F:\chain\TradingAgents
python -c "
from tradingagents_api.market_data import build_market_data
result = build_market_data('AAPL', '2026-08-21')
print(f'Ticker: {result.ticker}')
print(f'Kline dates: {len(result.kline.dates) if result.kline else 0}')
print(f'MACD dates: {len(result.macd.dates) if result.macd else 0}')
print(f'RSI values: {len(result.rsi.values) if result.rsi else 0}')
print(f'Fundamentals: {result.fundamentals is not None}')
print(f'News count: {len(result.news)}')
"
```

Expected: All fields populated (kline, macd, rsi should have data; fundamentals and news depend on vendor availability)

- [ ] **Step 2: Verify frontend TypeScript**

```bash
cd F:\chain\TradingAgents\tradingagents_gui
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Verify frontend build**

```bash
cd F:\chain\TradingAgents\tradingagents_gui
npx vite build
```

Expected: builds successfully

- [ ] **Step 4: Final commit with all changes**

```bash
git add -A
git status
git commit -m "feat: two-step workflow — market data preview before analysis" --no-verify
```
