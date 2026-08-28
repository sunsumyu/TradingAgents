import { Suspense, lazy, useEffect, Component, type ReactNode } from "react";
import { api } from "./lib/api";
import { saveConfig, type AnalysisConfig } from "./lib/types";
import { useAnalysisStore } from "./stores/useAnalysisStore";
import { useConfigStore } from "./stores/useConfigStore";
import { useMarketDataStore } from "./stores/useMarketDataStore";
import TopBar from "./components/TopBar";
import ConfigPanel from "./components/ConfigPanel";
import ProgressPanel from "./components/ProgressPanel";

const ReportPanel = lazy(() => import("./components/ReportPanel"));
const MarketDataPanel = lazy(() => import("./components/MarketDataPanel"));
const ScreenerPanel = lazy(() => import("./components/screener/ScreenerPanel"));
const PortfolioPanel = lazy(() => import("./components/portfolio/PortfolioPanel"));

// ── Error Boundary ──────────────────────────────────────────────
class ErrorBoundary extends Component<{ children: ReactNode; onReset?: () => void }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(err: unknown) {
    return { error: err instanceof Error ? err.message : String(err) };
  }
  render() {
    if (this.state.error) {
      return (
        <div className="p-6 text-center">
          <p className="text-red-400 text-sm mb-3">组件渲染出错: {this.state.error}</p>
          <button className="btn-primary text-sm" onClick={() => { this.setState({ error: null }); this.props.onReset?.(); }}>
            返回重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const phase = useAnalysisStore((s) => s.phase);
  const report = useAnalysisStore((s) => s.report);
  const config = useConfigStore((s) => s.config);
  const backendOnline = useConfigStore((s) => s.backendOnline);
  const navigateTo = useAnalysisStore((s) => s.navigateTo);
  const startAnalysis = useAnalysisStore((s) => s.startAnalysis);
  const loadYamlConfig = useConfigStore((s) => s.loadConfig);
  const connectWithRetry = useConfigStore((s) => s.connectWithRetry);
  const updateConfig = useConfigStore((s) => s.updateConfig);
  const fetchMarketData = useMarketDataStore((s) => s.fetchMarketData);

  // ── Load config from YAML + connect to backend on mount ────────────────
  useEffect(() => {
    loadYamlConfig();
    connectWithRetry();
  }, []);

  // ── Check for existing checkpoint when ticker changes ─────────────────
  useEffect(() => {
    if (!config.ticker || !backendOnline) return;
    let cancelled = false;
    api.getCheckpoint(config.ticker).then((info) => {
      if (!cancelled) useAnalysisStore.setState({ checkpointInfo: info });
    }).catch(() => {
      if (!cancelled) useAnalysisStore.setState({ checkpointInfo: null });
    });
    return () => { cancelled = true; };
  }, [config.ticker, backendOnline]);

  // ── Cleanup SSE stream on unmount ─────────────────────────────────────
  useEffect(() => {
    return () => useAnalysisStore.getState()._closeStream?.();
  }, []);

  // ── Handlers ──────────────────────────────────────────────────────────
  const handleConfigChange = (next: AnalysisConfig) => {
    updateConfig(next);
  };

  const handleLoadMarketData = () => {
    saveConfig(config);
    fetchMarketData(config.ticker, config.date);
    navigateTo("market_data");
  };

  const handleAnalyze = (resume: boolean = false) => {
    saveConfig(config);
    startAnalysis(config, resume);
  };

  const handleScreenerAnalyze = (ticker: string) => {
    const next = { ...config, ticker };
    updateConfig(next);
    navigateTo("config");
  };

  return (
    <div className="h-full flex flex-col">
      <TopBar />

      {phase === "config" && (
        <ConfigPanel
          config={config}
          onChange={handleConfigChange}
          onAnalyze={handleAnalyze}
          onMarketData={handleLoadMarketData}
          onScreener={() => navigateTo("screener")}
          onPortfolio={() => navigateTo("portfolio")}
        />
      )}

      {phase === "screener" && (
        <ErrorBoundary onReset={() => navigateTo("config")}>
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-[#787B86]">加载中...</div>}>
          <ScreenerPanel
            onBack={() => navigateTo("config")}
            onAnalyzeTicker={handleScreenerAnalyze}
          />
        </Suspense>
        </ErrorBoundary>
      )}

      {phase === "portfolio" && (
        <ErrorBoundary onReset={() => navigateTo("config")}>
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-[#787B86]">加载中...</div>}>
          <PortfolioPanel
            onBack={() => navigateTo("config")}
          />
        </Suspense>
        </ErrorBoundary>
      )}

      {phase === "market_data" && (
        <ErrorBoundary onReset={() => navigateTo("config")}>
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-[#787B86]">加载中...</div>}>
          <MarketDataPanel />
        </Suspense>
        </ErrorBoundary>
      )}

      {phase === "analyzing" && (
        <ProgressPanel
          ticker={config.ticker}
          date={config.date}
          selectedAnalysts={config.analysts}
        />
      )}

      {phase === "report" && report && (
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-text-secondary">加载中...</div>}>
          <ReportPanel />
        </Suspense>
      )}

      {phase === "error" && (
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <div className="text-down text-[14px]">{useAnalysisStore.getState().error}</div>
          <button className="btn-ghost" onClick={() => navigateTo("config")}>
            返回配置
          </button>
        </div>
      )}
    </div>
  );
}
