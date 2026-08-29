# Report Visualization Spec

## Problem Statement

The current TradingAgents analysis reports are entirely text-based — a markdown document rendered as plain HTML with no charts, no visual indicators, and no data-driven graphics. Traders and analysts must read through dense paragraphs to extract signals like price trends, MACD crossovers, or RSI levels, when these patterns are inherently visual and best understood through charts. The exported HTML file is a flat markdown dump with no interactivity.

## Solution

Add interactive ECharts-powered visualizations to both the GUI report panel and the exported HTML files. The backend will produce structured chart data alongside the existing markdown report, and the frontend will render six chart types: K-line candlestick, MACD, RSI, Bollinger Bands, a signal dashboard with radar scoring, and a fund flow chart. The exported HTML will bundle ECharts inline for full offline interactivity.

## User Stories

1. As a trader viewing the report in the GUI, I want to see a K-line candlestick chart with moving averages so that I can visually assess price trends at a glance.
2. As a trader viewing the report in the GUI, I want to see a MACD chart with histogram and signal lines so that I can identify momentum shifts without reading text descriptions.
3. As a trader viewing the report in the GUI, I want to see an RSI chart with overbought/oversold zones highlighted so that I can quickly gauge whether the stock is stretched.
4. As a trader viewing the report in the GUI, I want to see a Bollinger Bands chart with the current price marked so that I can see volatility context and mean-reversion potential.
5. As a trader viewing the report in the GUI, I want to see a signal dashboard with a gauge indicator and radar chart of dimension scores so that I can grasp the overall recommendation and its components instantly.
6. As a trader viewing the report in the GUI, I want to see a fund flow chart showing northbound, main force, and retail flows so that I can assess capital movement visually.
7. As a trader exporting the report as HTML, I want the exported file to contain the same interactive charts so that I can share a rich visual report with colleagues.
8. As a trader exporting the report as HTML, I want the exported file to work offline without external dependencies so that I can open it on any machine.
9. As a trader viewing the report, I want charts to animate when they load (number counting, gauge needle rotation, histogram bar expansion) so that the data feels alive and draws my attention.
10. As a trader viewing the K-line chart, I want to zoom and pan along the time axis so that I can focus on specific date ranges.
11. As a trader hovering over any chart point, I want a tooltip showing the exact values (date, OHLCV, indicator values) so that I can read precise numbers.
12. As a trader, I want the charts to be responsive so that they display correctly on different screen sizes.
13. As a developer, I want the chart data to be optional in the API response so that existing clients without chart support continue to work unchanged.
14. As a developer, I want the chart data generation to be a pure function of the final analysis state so that it is testable in isolation.
15. As a developer, I want the chart components to accept data as props so that they are decoupled from data fetching.
16. As a trader, I want the signal dashboard to color-code Buy as green, Sell as red, and Hold as neutral so that the signal is immediately recognizable.
17. As a trader, I want the K-line chart to overlay MA5, MA10, MA20 lines by default so that I can see short-, medium-, and long-term trends together.
18. As a trader, I want the MACD histogram bars to expand outward from the zero line with animation so that momentum direction is visually intuitive.
19. As a trader, I want the RSI chart to shade the overbought zone (above 70) in red and the oversold zone (below 30) in green so that extreme readings are visually obvious.
20. As a trader, I want the fund flow chart to use a stacked bar layout so that I can see the composition of daily capital flows at a glance.
21. As a trader, I want the radar chart in the dashboard to show scores for technical analysis, sentiment, fundamentals, and news so that I can see which dimensions drove the signal.
22. As a trader, I want the exported HTML to preserve the TradingView-style dark theme so that the visual experience is consistent with the GUI.
23. As a trader, I want the charts to appear above the markdown report text so that I see the visual summary before reading the detailed analysis.
24. As a trader, I want the K-line chart to show volume bars below the candlestick chart in a linked sub-chart so that I can correlate price movement with volume.

## Implementation Decisions

### Backend: Chart Data Construction

A new pure function `build_chart_data(final_state, ticker, date)` will be added to the runner module. This function receives the merged LangGraph state dict and returns an optional `ChartData` Pydantic model. It will:

- Parse OHLCV CSV data from `final_state` (the market analyst stores raw CSV in the state).
- Parse technical indicator strings from `get_stock_stats_indicators_window` format (`"date: value\n"`) into structured lists.
- Extract the trading signal and confidence from the final decision text.
- Extract dimension scores by parsing the analyst reports for rating keywords.

The function is idempotent and has no side effects — it only reads from `final_state` and returns a structured model.

### Backend: Schema Changes

`ReportResponse` gains an optional `chart_data` field:

```python
class ReportResponse(BaseModel):
    ticker: str
    signal: str
    report_md: str
    sections: dict[str, str] = Field(default_factory=dict)
    chart_data: ChartData | None = Field(default=None, description="Structured chart data for visualization")
```

The field defaults to `None` so that existing API consumers are unaffected. The `ChartData` model is composed of six optional sub-models (`KlineData`, `MacdData`, `RsiData`, `BollingerData`, `DashboardData`, `FundFlowData`), each only populated when the corresponding data is available.

### Backend: Data Parsing

Two parsing utilities will be added:

1. `parse_ohlcv_csv(csv_text: str) -> list[dict]` — parses the CSV output of `get_YFin_data_online` into a list of `{date, open, high, low, close, adj_close, volume}` dicts. Skips comment lines starting with `#`.

2. `parse_indicator_text(text: str) -> dict` — parses the formatted output of `get_stock_stats_indicators_window` into `{dates: list[str], values: list[float]}` by extracting lines matching the `YYYY-MM-DD: value` pattern.

### Frontend: Component Architecture

A new `ReportCharts` component will be created as the top-level chart container. It receives `ChartData` as a prop and conditionally renders sub-chart components:

- `KlineChart` — ECharts candlestick + volume + MA overlay
- `MacdChart` — ECharts bar + line combination
- `RsiChart` — ECharts area chart with horizontal reference lines
- `BollingerChart` — ECharts line chart with area fill
- `SignalDashboard` — ECharts gauge + radar combination
- `FundFlowChart` — ECharts stacked bar chart

Each chart component is a pure presentational component: it receives typed data props and returns JSX. No data fetching, no side effects beyond ECharts initialization.

### Frontend: ECharts Integration

ECharts will be imported as an npm dependency (`echarts` + `echarts-for-react`). Charts use the dark theme matching the existing TradingView-style color palette (`#131722` background, `#D1D4DC` text, `#2962FF` accent, `#089981` green, `#F23645` red).

### Frontend: HTML Export

The `saveHtml` function in `ReportPanel` will be rewritten to:

1. Fetch `echarts.min.js` from the npm package at build time and embed it as a string constant.
2. Generate a `<script>` block that calls `echarts.init()` on each chart container div and passes the serialized `chart_data` as JSON.
3. Include all chart containers above the markdown report content.
4. Preserve the dark theme CSS and the markdown-to-HTML conversion for the text report.

The exported HTML will be a single self-contained file with no external dependencies.

### Frontend: Data Animation

ECharts' built-in animation system will handle:
- Gauge needle rotation on the signal dashboard (`animationDuration: 1500`)
- K-line candlestick and volume bar entrance animation
- MACD histogram bar expansion from zero line
- RSI area fill animation
- Radar chart polygon drawing animation

Custom number-counting animations for dashboard scores will use CSS `@keyframes` with `counter()` or a lightweight JS counter.

## Testing Decisions

### What Makes a Good Test

Tests should verify external behavior (input-output contracts) rather than implementation details. For chart data construction, this means testing that given a specific `final_state` dict, the output `ChartData` has the expected structure and values. For parsing utilities, this means testing that given a specific string format, the output is correctly structured.

### Backend Unit Tests

**Module**: `tests/test_chart_data.py`

Tests for `build_chart_data`:
1. Given a `final_state` with market report CSV data, verify `chart_data.kline` is populated with correct OHLCV arrays.
2. Given a `final_state` with indicator text for MACD, verify `chart_data.macd` has matching dates, macd, signal, and histogram arrays.
3. Given a `final_state` with RSI indicator text, verify `chart_data.rsi` values are numeric and dates align.
4. Given a `final_state` with Bollinger band indicators, verify upper > middle > lower for all dates.
5. Given a `final_state` with a "Buy" signal, verify `chart_data.dashboard.signal` is "Buy" and confidence is positive.
6. Given a `final_state` missing market data, verify `chart_data.kline` is `None` (graceful degradation).
7. Given a `final_state` with all data missing, verify `chart_data` has all sub-models as `None`.

Tests for `parse_ohlcv_csv`:
8. Given valid CSV with comment headers, verify correct parsing into date/open/high/low/close/volume records.
9. Given empty CSV, verify empty list output.
10. Given CSV with malformed rows, verify those rows are skipped without raising.

Tests for `parse_indicator_text`:
11. Given valid indicator text with date-value pairs, verify correct extraction.
12. Given text with "N/A: Not a trading day" entries, verify those dates are excluded from output.
13. Given empty text, verify empty dict output.

### API Contract Tests

**Module**: `tests/test_report_response_chart_data.py`

14. Given a `ReportResponse` with `chart_data=None`, verify JSON serialization omits the field (or serializes as `null`).
15. Given a `ReportResponse` with a full `ChartData`, verify round-trip serialization/deserialization preserves all values.

### Prior Art

Existing tests in `tests/test_reporting.py` test `write_report_tree` output structure. The new chart data tests follow the same pattern: pure function tests with deterministic inputs and expected outputs, using pytest fixtures for mock data.

## Out of Scope

- Real-time streaming of chart data during analysis (charts are post-analysis only).
- Historical backtesting visualization.
- Custom chart configurations or user-selected indicator combinations.
- Mobile-specific responsive layouts beyond basic viewport scaling.
- Chart export to PNG/SVG from the GUI (can be added later via ECharts built-in `getDataURL`).
- Testing frontend React components (no existing vitest/jest infrastructure in the GUI project).

## Further Notes

- The `chart_data` field is backward-compatible: clients that don't request it simply ignore it, and the field defaults to `None`.
- ECharts bundle size (~1MB minified) will increase the exported HTML file from ~100KB to ~1.2MB. This is acceptable for an analysis report artifact.
- The chart data construction runs once after analysis completes, not per-render, so performance is not a concern.
- If the backend cannot retrieve historical price data (e.g., network failure), charts degrade gracefully: sub-models are `None` and the frontend renders the markdown report without charts.
