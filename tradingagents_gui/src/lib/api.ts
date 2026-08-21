import type {
  AnalysisConfig,
  AnalyzeRequest,
  AnalyzeResponse,
  ModelInfo,
  ProgressEvent,
  ProviderInfo,
  ReportResponse,
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
  async startAnalysis(config: AnalysisConfig): Promise<AnalyzeResponse> {
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
};
