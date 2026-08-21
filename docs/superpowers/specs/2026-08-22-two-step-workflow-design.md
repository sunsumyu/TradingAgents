# Design: Two-Step Workflow — Market Data Preview

## Problem

Currently, the user inputs a ticker and config, then immediately starts a 5-20 minute multi-agent analysis with no way to preview the stock data first. This is like asking someone to commit to a trade decision without letting them look at a chart first.

## Goal

Split the workflow into two distinct steps:
1. **Step 1: Market Data Preview** — User enters a ticker and sees charts, technical indicators, fundamentals, and news. They can review the data and decide whether to proceed.
2. **Step 2: Full Analysis** — User clicks "开始分析" and the existing multi-agent analysis runs as before.

## Architecture

### Flow

```
ConfigPanel (input ticker) → [查看数据] → MarketDataPanel (charts + data) → [开始分析] → ProgressPanel → ReportPanel
                             [直接分析] ─────────────────────────────────→ ProgressPanel → ReportPanel
```

- ConfigPanel gains two action buttons: "查看数据" (preview) and "直接分析" (skip to analysis)
- MarketDataPanel is a new page that displays charts + fundamentals + news
- The existing analysis flow remains unchanged — clicking "开始分析" on MarketDataPanel triggers the same `startAnalysis` function

### App.tsx State Machine

```typescript
type Phase = "config" | "market_data" | "analyzing" | "report" | "error";
```

New `market_data` phase:
- `config` → user clicks "查看数据" → `market_data` (calls new API)
- `market_data` → user clicks "开始分析" → `analyzing` (existing flow)
- `config` → user clicks "直接分析" → `analyzing` (existing flow, skips preview)

## Backend

### New API Endpoint: `POST /api/market-data`

**Request:**
```json
{
  "ticker": "AAPL",
  "date": "2026-08-22"
}
```

**Response:**
```json
{
  "ticker": "AAPL",
  "date": "2026-08-22",
  "kline": { "dates": [...], "ohlc": [...], "volumes": [...], "ma5": [...], "ema12": [...], "kdj_k": [...] },
  "macd": { "dates": [...], "macd": [...], "signal": [...], "histogram": [...] },
  "rsi": { "dates": [...], "values": [...] },
  "bollinger": { "dates": [...], "upper": [...], "middle": [...], "lower": [...], "close": [...] },
  "fundamentals": {
    "market_cap": 3450000000000,
    "pe_ratio": 32.1,
    "forward_pe": 28.5,
    "pb_ratio": 45.2,
    "eps_ttm": 6.42,
    "dividend_yield": 0.005,
    "beta": 1.2,
    "fifty_two_week_high": 199.62,
    "fifty_two_week_low": 164.08,
    "fifty_day_average": 195.89,
    "two_hundred_day_average": 188.45,
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "name": "Apple Inc."
  },
  "news": [
    { "title": "...", "publisher": "Reuters", "link": "https://...", "pub_date": "2026-08-21", "summary": "..." }
  ],
  "fund_flow": { "dates": [...], "northbound": [...], "mainForce": [...], "retail": [...] }
}
```

### Implementation

**`tradingagents_api/market_data.py`** (new file):

```python
def build_market_data(ticker: str, date: str) -> MarketDataResponse:
    """Fetch chart data, fundamentals, and news without running agents."""
    # 1. Reuse existing build_chart_data with empty final_state for charts
    # 2. Call route_to_vendor("get_fundamentals", ticker, date) for fundamentals
    # 3. Call route_to_vendor("get_news", ticker, start_date, date) for news
    # 4. Return combined response
```

Key: `build_chart_data(final_state={}, ticker, date)` already works with empty state — chart data fetching is independent of agent output. We just need to extract it into a standalone call.

**`tradingagents_api/schemas.py`** additions:

```python
class FundamentalsData(BaseModel):
    market_cap: float | None = None
    pe_ratio: float | None = None
    forward_pe: float | None = None
    pb_ratio: float | None = None
    eps_ttm: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    fifty_day_average: float | None = None
    two_hundred_day_average: float | None = None
    sector: str | None = None
    industry: str | None = None
    name: str | None = None

class NewsItem(BaseModel):
    title: str
    publisher: str | None = None
    link: str | None = None
    pub_date: str | None = None
    summary: str | None = None

class MarketDataResponse(BaseModel):
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

**`tradingagents_api/server.py`** addition:

```python
@app.post("/api/market-data")
async def market_data(request: MarketDataRequest):
    result = build_market_data(request.ticker, request.date)
    return result
```

## Frontend

### New Types (`tradingagents_gui/src/lib/types.ts`)

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

### New Component: `MarketDataPanel.tsx`

Layout (top to bottom):
1. **Top bar**: Back button, ticker name, signal badge (if any), config summary, "开始分析" button
2. **Fundamental cards row**: Market cap, PE, PB, 52-week high/low, EPS — compact card grid
3. **K-line chart**: Full width, with TradingView-style indicator parameter bar (reuses existing `KlineChart`)
4. **Technical indicators grid**: MACD | RSI | Bollinger in 3-column grid (reuses existing components)
5. **Fund flow**: Full width (reuses existing `FundFlowChart`)
6. **News feed**: Scrollable list with title, publisher, date, expandable summary

### ConfigPanel Changes

Add "查看数据" button alongside the existing "开始分析" button:

```
[查看数据]  [直接分析]
```

- "查看数据" calls `api.getMarketData(config)` → sets phase to `market_data`
- "直接分析" calls existing `startAnalysis()` → sets phase to `analyzing`

### API Client (`tradingagents_gui/src/lib/api.ts`)

Add new method:

```typescript
async getMarketData(ticker: string, date: string): Promise<MarketDataResponse> {
  const resp = await fetch(`${BASE}/api/market-data`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, date }),
  });
  if (!resp.ok) throw new Error(`Market data request failed: ${resp.status}`);
  return resp.json();
}
```

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `tradingagents_api/market_data.py` | Standalone market data fetching (no agents) |
| `tradingagents_gui/src/components/MarketDataPanel.tsx` | Market data preview page |
| `tradingagents_gui/src/components/charts/FundamentalCards.tsx` | Fundamentals display cards |
| `tradingagents_gui/src/components/charts/NewsFeed.tsx` | News list component |

### Modified Files
| File | Change |
|------|--------|
| `tradingagents_api/schemas.py` | Add FundamentalsData, NewsItem, MarketDataResponse models |
| `tradingagents_api/server.py` | Add `/api/market-data` endpoint |
| `tradingagents_gui/src/App.tsx` | Add `market_data` phase, wire up new flow |
| `tradingagents_gui/src/lib/types.ts` | Add frontend types |
| `tradingagents_gui/src/lib/api.ts` | Add `getMarketData()` method |
| `tradingagents_gui/src/components/ConfigPanel.tsx` | Add "查看数据" button |

## Data Dependencies

All market data can be fetched **independently** without running agents:

| Data Type | Source | Agent Required? |
|-----------|--------|-----------------|
| K-line OHLCV | `route_to_vendor("get_stock_data", ...)` | No |
| Technical indicators (24 types) | `route_to_vendor("get_indicators", ...)` | No |
| KDJ | Computed from OHLCV locally | No |
| Fundamentals | `route_to_vendor("get_fundamentals", ...)` | No |
| News | `route_to_vendor("get_news", ...)` | No |
| Fund flow (A-share) | `route_to_vendor("get_fund_flow", ...)` | No |
| Dashboard (signal/confidence) | Agent analysis output | **Yes** — not available in Step 1 |

## Out of Scope

- Multi-timeframe K-lines (weekly/monthly) — future enhancement
- Real-time streaming quotes — future enhancement
- Options data — not supported by current data layer
- Dashboard/signal badge on MarketDataPanel — only available after full analysis
