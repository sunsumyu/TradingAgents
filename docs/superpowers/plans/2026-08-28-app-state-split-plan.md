# Plan: App.tsx State Split to Zustand Stores

## Goal

Split App.tsx's 11 useState + 2 useRef hooks into three domain-scoped Zustand stores. App.tsx becomes a ~60-line thin routing layer. No API changes, no new features, no backend modifications.

## Reference Pattern

`useChartStore.ts` — single `create()` call, no middleware, `set<FieldName>` naming, `reset()` action, `ChartState & ChartActions` merged type.

## New Files

### 1. `tradingagents_gui/src/stores/useAnalysisStore.ts` (~180 lines)

**State:**
```
phase: Phase                      (default: "config")
events: ProgressEvent[]           (default: [])
streamingText: string             (default: "")
streamingAgent: string            (default: "")
report: ReportResponse | null     (default: null)
error: string                     (default: "")
taskId: string | null             (default: null)
checkpointInfo: { has_checkpoint: boolean; step: number | null } | null
isAnalyzing: boolean              (default: false)
closeStream: (() => void) | null  (internal, for SSE cleanup)
```

**Actions:**
- `navigateTo(phase)` — sets phase
- `startAnalysis(request, resume?)` — saves config, resets events/error, calls api.startAnalysis, opens SSE stream, stores closeStream
- `cancelAnalysis()` — calls closeStream(), resets to config phase
- `fetchReport(taskId)` — polls api.getReport up to 240x at 5s intervals
- `onProgressEvent(ev)` — appends to events (keep last 200)
- `onToken(agent, token)` — updates streamingText/streamingAgent
- `fetchCheckpoint(ticker)` — calls api.getCheckpoint, sets checkpointInfo
- `reset()` — clears all state, closes stream if active

**Side effects:** SSE stream open/close, report polling, checkpoint detection. All async logic that was in App.tsx callbacks moves here.

### 2. `tradingagents_gui/src/stores/useConfigStore.ts` (~120 lines)

**State:**
```
config: AnalysisConfig            (default: DEFAULT_CONFIG)
backendOnline: boolean            (default: false)
backendStatus: "connecting" | "failed" | "idle"  (default: "connecting")
```

**Actions:**
- `updateConfig(config)` — sets config, saves to localStorage, POSTs to YAML
- `loadConfig()` — fetches from server API + localStorage, merges, sets config
- `testConnection()` — calls api.healthCheck, sets backendOnline/backendStatus
- `reset()` — resets to defaults

**Side effects:** localStorage read/write, YAML save. On mount, App.tsx calls `loadConfig()` and `testConnection()`.

### 3. `tradingagents_gui/src/stores/useMarketDataStore.ts` (~60 lines)

**State:**
```
data: MarketDataResponse | null   (default: null)
isLoading: boolean                (default: false)
error: string                     (default: "")
```

**Actions:**
- `fetchMarketData(ticker, date)` — calls api.getMarketData, sets data/error
- `reset()` — clears data/error/isLoading

## Modified Files

### 4. `tradingagents_gui/src/App.tsx` (378 → ~80 lines)

**Remove:** All 11 useState, 2 useRef, all callback functions (handleConfigChange, checkHealth, loadMarketData, startAnalysis, pollReport, cancelAnalysis, handleScreenerAnalyze).

**Keep:** Phase routing JSX (the switch/if blocks that render child components).

**Add:** Store imports, mount effects (loadConfig, testConnection on mount), callback wrappers that call store actions.

**Before:**
```tsx
const [config, setConfig] = useState<AnalysisConfig>(loadConfig());
const [phase, setPhase] = useState<Phase>("config");
const [backendOnline, setBackendOnline] = useState(false);
// ... 8 more useState + 2 useRef
```

**After:**
```tsx
const phase = useAnalysisStore(s => s.phase);
const config = useConfigStore(s => s.config);
const backendOnline = useConfigStore(s => s.backendOnline);
// Store actions called directly in callbacks
```

### 5. `tradingagents_gui/src/components/TopBar.tsx`

**Remove props:** `backendOnline`, `backendStatus`
**Add:** Import `useConfigStore`, read `s.backendOnline` and `s.backendStatus` directly.

### 6. `tradingagents_gui/src/components/ConfigPanel.tsx`

**Remove props:** `config`, `onChange`, `backendOnline`, `backendStatus`, `onTestConnection`, `onFetchModels`, `checkpoint`, `onResume`
**Add:** Import `useConfigStore` and `useAnalysisStore`, read state directly.
**Keep props:** `onAnalyze` (callback to start analysis), `onMarketData`, `onScreener`, `onPortfolio` — these are cross-domain actions.
**Keep local state:** platformModels, platformSelections, platformLoading, testing, manualTesting, tickerHistory, showHistory.

### 7. `tradingagents_gui/src/components/ProgressPanel.tsx`

**Remove props:** `events`, `streamingText`, `streamingAgent`, `onCancel`
**Add:** Import `useAnalysisStore`, read state directly.
**Keep props:** `ticker`, `date`, `selectedAnalysts` — derived from config, passed through.

### 8. `tradingagents_gui/src/components/ReportPanel.tsx`

**Remove props:** `ticker`, `signal`, `reportMd`, `sections`, `chartData`, `onBack`
**Add:** Import `useAnalysisStore`, read `s.report` directly, destructure in component.

### 9. `tradingagents_gui/src/components/MarketDataPanel.tsx`

**Remove props:** `data`, `isLoading`, `error`, `onBack`, `isAnalyzing`
**Add:** Import `useMarketDataStore` and `useAnalysisStore`, read state directly.
**Keep props:** `onAnalyze` — cross-domain action.

## Migration Order (6 steps)

**Step 1:** Create `stores/` directory and all 3 store files. No existing code changes yet.

**Step 2:** Migrate `useAnalysisStore` — modify App.tsx to use store for phase, events, streaming, report, error, taskId, checkpoint. Modify ProgressPanel, ReportPanel to read from store. This is the biggest change (7 state fields + SSE wiring).

**Step 3:** Migrate `useConfigStore` — modify App.tsx to use store for config, backendOnline, backendStatus. Modify TopBar, ConfigPanel to read from store. Config persistence moves to store.

**Step 4:** Migrate `useMarketDataStore` — modify App.tsx to use store for marketData, isLoading. Modify MarketDataPanel to read from store.

**Step 5:** Clean up App.tsx — remove dead code, verify all callbacks are thin wrappers around store actions.

**Step 6:** Verify — run `npm run build` (or `npx tsc --noEmit`), manual smoke test, ensure no regressions.

## Verification

- `npx tsc --noEmit` (TypeScript compilation)
- `npm run build` (Vite build)
- Manual: open app → configure → analyze → view report → back → market data → back
- Manual: checkpoint resume works
- Manual: SSE streaming displays correctly
- Manual: config persists across refresh
- Manual: screener → analyze ticker → back to config works
