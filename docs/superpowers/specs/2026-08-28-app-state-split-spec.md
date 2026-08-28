# Spec: App.tsx State Split to Zustand Stores

## Problem Statement

App.tsx is a god-component with 378 lines, 11 `useState` hooks, and 2 `useRef` hooks. All application state lives here and is passed down via props to child components (ConfigPanel, ProgressPanel, MarketDataPanel, ReportPanel, TopBar, ScreenerPanel, PortfolioPanel). This creates:

1. **Re-render cascade** — any state change re-renders the entire component tree, including components that don't consume the changed state.
2. **Props drilling** — `config` flows through 3 levels; `backendOnline` flows through 2 levels; callbacks like `onAnalyze`, `onBack`, `onMarketData` are threaded through every child.
3. **God-component complexity** — App.tsx owns analysis orchestration (SSE streaming, task lifecycle), config persistence, backend health checking, and page routing — all interleaved.
4. **Inconsistent patterns** — the TradingView chart domain already uses Zustand (`useChartStore`), but every other domain uses `useState` + prop drilling.

## Solution

Split App.tsx's 11 `useState` hooks into three domain-scoped Zustand stores, following the existing `useChartStore` precedent. App.tsx becomes a ~60-line thin routing layer that composes stores and renders the active phase.

## User Stories

1. As a developer, I want each domain's state co-located in its own store, so that I can modify analysis state without triggering ConfigPanel re-renders.
2. As a developer, I want child components to read state directly from stores (e.g., `useAnalysisStore(s => s.phase)`), so that props drilling is eliminated.
3. As a developer, I want the analysis lifecycle (start, stream, complete, error) encapsulated in a single store with actions, so that the logic is testable in isolation.
4. As a developer, I want config persistence (localStorage read/write) to live inside `useConfigStore`, so that `loadConfig`/`saveConfig` calls are colocated with the state they manage.
5. As a developer, I want backend health checking to live in its own slice, so that TopBar and ConfigPanel can subscribe independently without re-rendering each other.
6. As a user, I want the app to feel faster when switching between config and analysis phases, so that only the affected components re-render.
7. As a user, I want my config changes to persist to localStorage automatically, so that I don't lose settings on refresh.
8. As a developer, I want the SSE stream lifecycle (open/close/cleanup) managed by store actions, so that `useRef` hacks are eliminated.
9. As a developer, I want to be able to add new stores (e.g., `usePortfolioStore`) without modifying App.tsx, so that the architecture scales.
10. As a developer, I want each store to have a `reset()` action, so that navigation between phases is clean.
11. As a developer, I want the `phase` routing state to be derived from the active store's state, so that there's a single source of truth for "which page am I on."
12. As a developer, I want progress events (`events[]`, `streamingText`, `streamingAgent`) scoped to the analysis store, so that they don't leak into unrelated components.
13. As a developer, I want error state to be part of the analysis store, so that error handling is colocated with the analysis that produced it.
14. As a developer, I want market data state (`marketData`, `_loadingMarketData`, `error`) scoped to its own store, so that MarketDataPanel can manage its own loading lifecycle.
15. As a developer, I want checkpoint state (`checkpointInfo`) to live in the analysis store, so that resume logic is colocated with the analysis lifecycle.
16. As a developer, I want `taskIdRef` and `closeStreamRef` replaced with store-managed state, so that imperative refs don't escape the store boundary.
17. As a developer, I want each store to be independently importable, so that components only pull in the state they need.
18. As a developer, I want the stores to use Zustand's `subscribe` for side effects (e.g., auto-persist config), so that useEffect hooks are minimized.
19. As a developer, I want the store types exported from a central location, so that TypeScript can infer state shapes consistently.
20. As a user, I want the "analyze" button to work exactly as before, so that the refactor is invisible.
21. As a user, I want the "back" button on MarketDataPanel and ReportPanel to work exactly as before, so that navigation is unaffected.
22. As a user, I want the SSE streaming progress to display identically, so that the refactor doesn't break real-time updates.
23. As a user, I want checkpoint resume to work exactly as before, so that interrupted analyses can still be resumed.
24. As a user, I want the screener and portfolio phases to work exactly as before, so that the refactor is scoped to state management.
25. As a developer, I want the store to expose a `startAnalysis` action that wraps `api.startAnalysis`, so that the API call and state update are atomic.
26. As a developer, I want the store to expose a `cancelAnalysis` action that calls the SSE close function, so that cleanup is encapsulated.
27. As a developer, I want the store to expose a `fetchReport` action that polls `api.getReport`, so that the report fetch lifecycle is managed in one place.
28. As a developer, I want the store to expose a `streamProgress` action that opens the SSE stream and wires up handlers, so that streaming logic doesn't leak into components.
29. As a developer, I want the store to handle 429 rate-limit retries internally, so that components don't need to know about retry logic.
30. As a developer, I want the store to expose a `loadConfig` action that reads from the backend API, so that config initialization is explicit.
31. As a developer, I want the store to expose a `saveConfig` action that persists to both local state and the backend, so that config is always in sync.
32. As a developer, I want the store to expose provider/model fetching actions, so that ConfigPanel doesn't need to manage loading state locally.
33. As a developer, I want the store to expose a `testConnection` action, so that the backend health check is a store concern, not a component concern.
34. As a developer, I want the store to expose a `fetchMarketData` action, so that MarketDataPanel's loading state is managed centrally.
35. As a developer, I want the store to expose a `navigateTo` action that sets the phase, so that navigation is a first-class store operation.
36. As a developer, I want the store to support `persist` middleware for config, so that localStorage is handled declaratively.
37. As a developer, I want the store to use `immer` middleware for immutable updates, so that nested state changes are ergonomic.
38. As a developer, I want the store to be debuggable via Zustand DevTools, so that state changes are traceable.
39. As a developer, I want the store to be testable with `renderHook` from `@testing-library/react`, so that store logic can be unit-tested without rendering.
40. As a developer, I want the store to expose derived selectors (e.g., `selectIsAnalyzing`, `selectIsConfigValid`), so that components don't compute derived state.

## Implementation Decisions

### Store Domain Boundaries

**Store 1: `useAnalysisStore`** — Analysis lifecycle, progress, report, error
- State: `phase`, `events[]`, `streamingText`, `streamingAgent`, `report`, `error`, `taskId`, `checkpointInfo`, `isAnalyzing`
- Actions: `startAnalysis`, `cancelAnalysis`, `fetchReport`, `streamProgress`, `reset`, `navigateTo`
- Side effects: SSE stream open/close, report polling, checkpoint detection
- Replaces: 7 useState hooks + 2 useRef hooks from App.tsx

**Store 2: `useConfigStore`** — Configuration, providers, models, backend health
- State: `config`, `backendOnline`, `backendStatus`, `providers[]`, `quickModels[]`, `deepModels[]`
- Actions: `loadConfig`, `saveConfig`, `fetchProviders`, `fetchModels`, `testConnection`, `updateConfig`, `reset`
- Side effects: localStorage persistence via Zustand `persist` middleware
- Replaces: 2 useState hooks from App.tsx (config, backendOnline/backendStatus)

**Store 3: `useMarketDataStore`** — Market data view
- State: `data`, `isLoading`, `error`
- Actions: `fetchMarketData`, `reset`
- Replaces: 2 useState hooks from App.tsx (marketData, _loadingMarketData)

**Existing store: `useChartStore`** — Unchanged (TradingView chart state)

### File Layout

```
tradingagents_gui/src/
├── stores/
│   ├── useAnalysisStore.ts    (~180 lines)
│   ├── useConfigStore.ts      (~120 lines)
│   └── useMarketDataStore.ts  (~60 lines)
├── lib/
│   └── useChartStore.ts       (existing, unchanged)
```

### Component Changes

**App.tsx** (378 → ~60 lines):
- Remove all useState/useRef hooks
- Import stores, wire `navigateTo` actions to callback props
- Compose child components with store selectors as props

**ConfigPanel.tsx** (682 lines):
- Replace `config` prop with `useConfigStore(s => s.config)`
- Replace `onChange` callback with `useConfigStore(s => s.updateConfig)`
- Replace `backendOnline`/`backendStatus` props with store selectors
- Replace `onTestConnection` with `useConfigStore(s => s.testConnection)`
- Replace `onFetchModels` with `useConfigStore(s => s.fetchModels)`
- Keep local state for UI-only concerns (platformModels, platformSelections, testing, manualTesting, tickerHistory, showHistory)

**ProgressPanel.tsx**:
- Replace `events`/`streamingText`/`streamingAgent` props with `useAnalysisStore` selectors
- Keep `ticker`/`date`/`selectedAnalysts` as props (derived from config, not analysis state)

**MarketDataPanel.tsx**:
- Replace `data`/`isLoading`/`error` props with `useMarketDataStore` selectors
- Replace `onBack` callback with `useAnalysisStore(s => s.navigateTo)`

**ReportPanel.tsx**:
- Replace `ticker`/`signal`/`reportMd`/`sections`/`chartData` props with `useAnalysisStore(s => s.report)` selector
- Replace `onBack` callback with `useAnalysisStore(s => s.navigateTo)`

**TopBar.tsx**:
- Replace `backendOnline`/`backendStatus` props with `useConfigStore` selectors

### Zustand Middleware Stack

```typescript
// useConfigStore — persist to localStorage
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// useAnalysisStore — immer for nested updates
import { immer } from 'zustand/middleware/immer'

// useMarketDataStore — no middleware needed
import { create } from 'zustand'
```

### Type Definitions

All store types are exported from `stores/` and co-located with the store. The existing `types.ts` types (`AnalysisConfig`, `ReportResponse`, `MarketDataResponse`, `ProgressEvent`) remain unchanged — stores consume them, not redefine them.

### SSE Stream Lifecycle

The SSE stream is opened by `useAnalysisStore.streamProgress()`:
1. Call `api.openProgressStream(taskId, onEvent, onError, onComplete)`
2. Store the close function in store state (`closeStream` field, replacing `closeStreamRef`)
3. On `cancelAnalysis`: call `closeStream()`, reset analysis state
4. On store `reset()`: call `closeStream()` if active, then clear state

### Config Persistence

`useConfigStore` uses Zustand `persist` middleware:
- Storage key: `"tradingagents-config"`
- Persists: `config` (AnalysisConfig)
- Does NOT persist: `backendOnline`, `backendStatus`, `providers`, `quickModels`, `deepModels` (ephemeral)

### Selectors

Each store exports named selectors for optimized re-renders:
```typescript
// useAnalysisStore
export const selectPhase = (s) => s.phase
export const selectIsAnalyzing = (s) => s.phase === 'analyzing'
export const selectReport = (s) => s.report
export const selectError = (s) => s.error

// useConfigStore
export const selectConfig = (s) => s.config
export const selectBackendOnline = (s) => s.backendOnline

// useMarketDataStore
export const selectMarketData = (s) => s.data
export const selectIsLoading = (s) => s.isLoading
```

## Testing Decisions

- **Store unit tests**: Test each store's actions in isolation using `renderHook` from `@testing-library/react`. Verify state transitions (e.g., `startAnalysis` → `phase === 'analyzing'`, `fetchReport` success → `phase === 'report'`).
- **Mock API layer**: All API calls (`api.startAnalysis`, `api.getReport`, etc.) are mocked at the module level. Stores should not make real HTTP calls in tests.
- **Regression tests**: Existing tests in `tests/` should continue to pass without modification, since the API layer is unchanged.
- **Prior art**: `useChartStore` already has this pattern. Follow its test structure.
- **No snapshot tests**: Store state shapes are tested via assertions, not snapshots.

## Out of Scope

- **Refactoring ConfigPanel's internal state** — the 7 local useState hooks in ConfigPanel (platformModels, platformSelections, etc.) stay local. They're UI-only concerns.
- **Refactoring ReportPanel's internal state** — the 7 local useState hooks (activeTab, tocWidth, etc.) stay local.
- **Adding new features** — this is a pure refactor. No new API calls, no new UI elements, no new routes.
- **Modifying the backend** — the Python API layer is untouched.
- **Refactoring types.ts** — the 611-line types file is a separate concern (Candidate #3 from the architecture review).
- **Adding new Zustand middleware** — no `devtools` or `subscribeWithSelector` middleware unless a specific need arises during implementation.

## Further Notes

- The existing `useChartStore` is the reference pattern. It uses `create()` from Zustand, has 14 setter actions, a `loadChartData` bulk updater, and a `reset` action. The new stores should follow this exact pattern.
- Zustand v5.0.15 is already installed. No dependency changes needed.
- The refactor should be done incrementally: first create the stores, then migrate one component at a time, verifying after each migration.
- The `phase` routing state in `useAnalysisStore` is the single source of truth for which page is active. Navigation is a store action, not a component-level concern.
