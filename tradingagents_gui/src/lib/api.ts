import type {
  AnalysisConfig,
  AnalyzeRequest,
  AnalyzeResponse,
  AstockFeatureEnvelope,
  BacktestRequest,
  BacktestResponse,
  ChartExportRequest,
  ModelInfo,
  NavPoint,
  PortfolioResponse,
  ProgressEvent,
  ProviderInfo,
  RealtimePrice,
  ReportResponse,
  ScreenerResponse,
  TradeRecord,
} from "./types";

const BASE_URL = "http://127.0.0.1:8420";

// ── Helpers ─────────────────────────────────────────────────────────────────────

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? body.message ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ── API client ──────────────────────────────────────────────────────────────────

export const api = {
  /** GET / — health check */
  async healthCheck(): Promise<boolean> {
    try {
      const res = await fetch(`${BASE_URL}/`, { signal: AbortSignal.timeout(3000) });
      return res.ok;
    } catch {
      return false;
    }
  },

  /** GET /api/today — server-side date (bypasses JS Date issues) */
  async getToday(): Promise<string> {
    try {
      const res = await fetch(`${BASE_URL}/api/today`);
      if (!res.ok) return "";
      const data = await res.json();
      return data.date || "";
    } catch {
      return "";
    }
  },

  /** GET /api/providers — full catalog */
  async getProviders(): Promise<ProviderInfo[]> {
    const res = await fetch(`${BASE_URL}/api/providers`);
    return handle<ProviderInfo[]>(res);
  },

  /** GET /api/models/{provider}?proxy_url=xxx&api_key=xxx */
  async getModels(provider: string, proxyUrl?: string, apiKey?: string): Promise<{
    name: string;
    api_key_env: string | null;
    quick: ModelInfo[];
    deep: ModelInfo[];
    source?: string;
  }> {
    const params = new URLSearchParams();
    if (proxyUrl) params.set("proxy_url", proxyUrl);
    if (apiKey) params.set("api_key", apiKey);
    const url = `${BASE_URL}/api/models/${encodeURIComponent(provider)}${params.toString() ? `?${params.toString()}` : ""}`;
    const res = await fetch(url);
    return handle(res);
  },

  /** POST /api/analyze — maps frontend config → backend AnalyzeRequest schema */
  async startAnalysis(config: AnalysisConfig, resume: boolean = false): Promise<AnalyzeResponse> {
    // Convert platform-based config to backend ModelConfig format
    const getPlatformModelConfig = (platformId: string, model: string) => {
      const platform = config.llm_platforms.find(p => p.id === platformId);
      if (!platform || !model) return null;
      return {
        provider: platform.provider,
        model: model,
        api_key: platform.api_key || null,
        backend_url: platform.backend_url || null,
      };
    };

    const req: AnalyzeRequest = {
      ticker: config.ticker,
      date: config.date,
      language: config.language,
      analysts: config.analysts,
      depth: config.depth,
      // Multi-platform LLM config
      quick_model: getPlatformModelConfig(config.quick_model.platform_id, config.quick_model.model),
      deep_model: getPlatformModelConfig(config.deep_model.platform_id, config.deep_model.model),
      // Legacy single-provider config (backward compatible)
      llm_provider: config.llm_provider,
      deep_think_llm: config.deep_think_llm,
      quick_think_llm: config.quick_think_llm,
      api_key: config.api_key || null,
      backend_url: config.llm_proxy_url || null,
      resume,
    };
    const res = await fetch(`${BASE_URL}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    return handle<AnalyzeResponse>(res);
  },

  /** GET /api/report/{task_id} — throws "Report not ready yet" when 202/404 */
  async getReport(taskId: string): Promise<ReportResponse> {
    const res = await fetch(`${BASE_URL}/api/report/${taskId}`);
    if (res.status === 202 || res.status === 404) {
      throw new Error("Report not ready yet");
    }
    return handle<ReportResponse>(res);
  },

  /** Open an SSE stream to /api/analyze/{task_id}/stream */
  openProgressStream(
    taskId: string,
    onEvent: (ev: ProgressEvent) => void,
    onComplete: () => void,
    onError: (msg: string) => void,
    onToken?: (agent: string, token: string) => void,
  ): () => void {
    const url = `${BASE_URL}/api/analyze/${taskId}/stream`;
    const es = new EventSource(url);

    es.addEventListener("progress", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as ProgressEvent;
        onEvent(data);
      } catch (err) {
        console.error("Bad progress event:", err);
      }
    });

    if (onToken) {
      es.addEventListener("token", (e) => {
        try {
          const data = JSON.parse((e as MessageEvent).data);
          onToken(data.agent, data.token);
        } catch {
          // ignore malformed token events
        }
      });
    }

    es.addEventListener("complete", () => {
      onComplete();
      es.close();
    });

    es.addEventListener("error", (e) => {
      // EventSource fires "error" both on server-sent `event: error` AND
      // on connection problems (e.g. backend crashed).  Distinguish them:
      // server-sent errors carry data; connection drops do not.
      const msg = (e as MessageEvent).data;
      if (typeof msg === "string" && msg) {
        try {
          const parsed = JSON.parse(msg);
          onError(parsed.message ?? msg);
        } catch {
          onError(msg);
        }
      } else {
        // Connection lost — surface a clear message so the UI doesn't
        // get stuck on a white/blank screen (phase stuck in "analyzing").
        onError("后端连接中断，分析已停止。请检查后端是否仍在运行。");
      }
      es.close();
    });

    return () => es.close();
  },

  /** GET /api/config — load config from YAML */
  async loadConfig(): Promise<{ config: Record<string, unknown> | null; path: string }> {
    const res = await fetch(`${BASE_URL}/api/config`);
    return handle<{ config: Record<string, unknown> | null; path: string }>(res);
  },

  /** POST /api/config — save config to YAML */
  async saveConfig(config: Record<string, unknown>): Promise<{ status: string; path: string }> {
    const res = await fetch(`${BASE_URL}/api/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config }),
    });
    return handle<{ status: string; path: string }>(res);
  },

  /** POST /api/market-data — fetch market data for a ticker and date */
  async getMarketData(ticker: string, date: string): Promise<import("./types").MarketDataResponse> {
    const resp = await fetch(`${BASE_URL}/api/market-data`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, date }),
    });
    if (!resp.ok) {
      throw new Error(`Market data request failed: ${resp.status}`);
    }
    return resp.json();
  },

  /** POST /api/chart-data — fetch chart data with configurable date range.
   *  ``interval`` ("1m"…"60m") selects minute bars; omit for daily bars. */
  async getChartData(
    ticker: string,
    date: string,
    days: number,
    signal?: AbortSignal,
    interval?: string | null,
  ): Promise<{
    ticker: string;
    date: string;
    days: number;
    interval?: string | null;
    kline?: import("./types").KlineData | null;
    macd?: import("./types").MacdData | null;
    rsi?: import("./types").RsiData | null;
    bollinger?: import("./types").BollingerData | null;
    fundFlow?: import("./types").FundFlowData | null;
  }> {
    const resp = await fetch(`${BASE_URL}/api/chart-data`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, date, days, interval: interval ?? null }),
      signal,
    });
    if (!resp.ok) {
      throw new Error(`Chart data request failed: ${resp.status}`);
    }
    return resp.json();
  },

  /** POST /api/realtime-prices - batch realtime quotes for the watchlist */
  async getRealtimePrices(
    tickers: string[],
    signal?: AbortSignal,
  ): Promise<Record<string, RealtimePrice>> {
    const resp = await fetch(`${BASE_URL}/api/realtime-prices`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers }),
      signal,
    });
    if (!resp.ok) {
      throw new Error(`Realtime prices request failed: ${resp.status}`);
    }
    return resp.json();
  },

  /** GET /api/checkpoints/{ticker} — check if a resumable checkpoint exists */
  async getCheckpoint(ticker: string): Promise<{
    ticker: string;
    has_checkpoint: boolean;
    step: number | null;
    date: string;
  }> {
    const resp = await fetch(`${BASE_URL}/api/checkpoints/${encodeURIComponent(ticker)}`);
    if (!resp.ok) {
      return { ticker, has_checkpoint: false, step: null, date: "" };
    }
    return resp.json();
  },

  /** POST /api/astock-features — A-stock data center feature (Phase 5).
   *  Single endpoint + feature dispatch table; ``data`` is the structured
   *  parser output for the feature, ``raw_md`` the verbatim markdown. */
  async getAstockFeature<T = Record<string, unknown>>(
    feature: string,
    ticker: string,
    date: string,
    signal?: AbortSignal,
    params?: Record<string, unknown>,
  ): Promise<AstockFeatureEnvelope<T>> {
    const resp = await fetch(`${BASE_URL}/api/astock-features`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feature, ticker, date, params: params ?? {} }),
      signal,
    });
    if (!resp.ok) {
      let detail = `Feature request failed: ${resp.status}`;
      try {
        const body = await resp.json();
        detail = body.detail ?? detail;
      } catch {
        /* not JSON */
      }
      throw new Error(detail);
    }
    return resp.json();
  },

  /** GET /api/portfolio — current portfolio with positions and P&L */
  async getPortfolio(): Promise<PortfolioResponse> {
    const resp = await fetch(`${BASE_URL}/api/portfolio`);
    return handle<PortfolioResponse>(resp);
  },

  /** POST /api/portfolio/trade — execute a simulated trade */
  async portfolioTrade(
    ticker: string,
    action: "buy" | "sell",
    quantity: number,
    price: number,
    name?: string,
    reason?: string,
  ): Promise<PortfolioResponse> {
    const resp = await fetch(`${BASE_URL}/api/portfolio/trade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, action, quantity, price, name: name ?? "", reason: reason ?? "" }),
    });
    if (!resp.ok) {
      let detail = `Trade failed: ${resp.status}`;
      try {
        const body = await resp.json();
        detail = body.detail ?? detail;
      } catch { /* not JSON */ }
      throw new Error(detail);
    }
    return resp.json();
  },

  /** GET /api/portfolio/history — trade history */
  async getPortfolioHistory(): Promise<TradeRecord[]> {
    const resp = await fetch(`${BASE_URL}/api/portfolio/history`);
    return handle<TradeRecord[]>(resp);
  },

  /** GET /api/portfolio/nav — NAV history for performance chart */
  async getPortfolioNav(): Promise<{ nav_history: NavPoint[] }> {
    const resp = await fetch(`${BASE_URL}/api/portfolio/nav`);
    return handle<{ nav_history: NavPoint[] }>(resp);
  },

  /** POST /api/portfolio/reset — reset portfolio */
  async resetPortfolio(initialCash: number = 1_000_000): Promise<PortfolioResponse> {
    const resp = await fetch(`${BASE_URL}/api/portfolio/reset?initial_cash=${initialCash}`, {
      method: "POST",
    });
    return handle<PortfolioResponse>(resp);
  },

  /** POST /api/screener — natural-language stock screener (Phase 6) */
  async runScreener(
    query: string,
    maxResults: number = 20,
    tickerHint?: string,
    signal?: AbortSignal,
  ): Promise<ScreenerResponse> {
    const resp = await fetch(`${BASE_URL}/api/screener`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, max_results: maxResults, ticker_hint: tickerHint ?? null }),
      signal,
    });
    if (!resp.ok) {
      let detail = `Screener request failed: ${resp.status}`;
      try {
        const body = await resp.json();
        detail = body.detail ?? detail;
      } catch {
        /* not JSON */
      }
      throw new Error(detail);
    }
    return resp.json();
  },

  /** POST /api/backtest - backtest the report's trade decision (ticket #6).
   *  503 carries the akquant install guidance in `detail`. */
  async runBacktest(req: BacktestRequest, signal?: AbortSignal): Promise<BacktestResponse> {
    const resp = await fetch(`${BASE_URL}/api/backtest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
    if (!resp.ok) {
      let detail = `回测请求失败: HTTP ${resp.status}`;
      try {
        const body = await resp.json();
        detail = body.detail ?? detail;
      } catch {
        /* not JSON */
      }
      throw new Error(detail);
    }
    return resp.json();
  },

  /** POST /api/chart-export - server-side high-DPI chart PNG export (ticket #7).
   *  Returns a Blob (image/png).  503 carries the matplotlib install guidance. */
  async exportChart(req: ChartExportRequest, signal?: AbortSignal): Promise<Blob> {
    const resp = await fetch(`${BASE_URL}/api/chart-export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
    if (!resp.ok) {
      let detail = `图表导出失败: HTTP ${resp.status}`;
      try {
        const body = await resp.json();
        detail = body.detail ?? detail;
      } catch {
        /* not JSON */
      }
      throw new Error(detail);
    }
    return resp.blob();
  },
};
