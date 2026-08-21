// ── API types matching tradingagents_api/schemas.py ────────────────────────────

/** A configured LLM platform (provider + auth) */
export interface LLMPlatform {
  id: string;           // unique identifier
  name: string;         // display name (e.g. "My OpenAI")
  provider: string;     // provider key (e.g. "openai", "anthropic")
  api_key: string;
  backend_url: string;
}

/** Model selection from configured platforms */
export interface ModelSelection {
  platform_id: string;  // reference to LLMPlatform.id
  model: string;        // model ID
}

/** Configuration for a single LLM model (provider + model + auth) - legacy */
export interface ModelConfig {
  provider: string;
  model: string;
  api_key?: string | null;
  backend_url?: string | null;
}

export interface AnalyzeRequest {
  ticker: string;
  date: string;
  language: string;
  analysts: string[];
  depth: string;
  // Multi-platform LLM config
  quick_model?: ModelConfig | null;
  deep_model?: ModelConfig | null;
  // Legacy single-provider config (backward compatible)
  llm_provider: string;
  deep_think_llm: string;
  quick_think_llm: string;
  api_key?: string | null;
  backend_url?: string | null;
}

export interface AnalyzeResponse {
  task_id: string;
  status: string;
}

export interface ProgressEvent {
  phase: string;
  agent: string;
  status: "in_progress" | "completed" | "error" | "pending" | string;
  message: string;
  timestamp: string;
}

export interface ReportResponse {
  ticker: string;
  signal: string;
  report_md: string;
  sections: Record<string, string>;
  chart_data?: ChartData | null;
}

// ── Chart visualization types (mirrors tradingagents_api/schemas.py) ──────────

export interface KlineData {
  dates: string[];
  ohlc: [number, number, number, number][]; // [open, close, low, high]
  volumes: number[];
  ma5?: (number | null)[];
  ma10?: (number | null)[];
  ma20?: (number | null)[];
  ma50?: (number | null)[];
  ema12?: (number | null)[];
  ema26?: (number | null)[];
  kdj_k?: (number | null)[];
  kdj_d?: (number | null)[];
  kdj_j?: (number | null)[];
}

export interface MacdData {
  dates: string[];
  macd: number[];
  signal: number[];
  histogram: number[];
}

export interface RsiData {
  dates: string[];
  values: number[];
}

export interface BollingerData {
  dates: string[];
  upper: number[];
  middle: number[];
  lower: number[];
  close: number[];
}

export interface DashboardData {
  signal: "Buy" | "Hold" | "Sell" | "Overweight" | "Underweight";
  confidence: number;
  scores: { name: string; value: number; max: number }[];
}

export interface FundFlowData {
  dates: string[];
  northbound: number[];
  mainForce: number[];
  retail: number[];
}

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

export interface ChartData {
  kline?: KlineData | null;
  macd?: MacdData | null;
  rsi?: RsiData | null;
  bollinger?: BollingerData | null;
  dashboard?: DashboardData | null;
  fundFlow?: FundFlowData | null;
}

export interface ModelInfo {
  label: string;
  id: string;
}

export interface StreamingToken {
  agent: string;
  token: string;
}

export interface ProviderInfo {
  name: string;
  api_key_env: string | null;
  models?: {
    quick: ModelInfo[];
    deep: ModelInfo[];
  };
}

// ── App-level config (persisted in localStorage + YAML) ────────────────────────

export interface AnalysisConfig {
  ticker: string;
  date: string;
  language: string;
  analysts: string[];
  depth: string;
  // Multi-platform LLM config
  llm_platforms: LLMPlatform[];
  quick_model: ModelSelection;
  deep_model: ModelSelection;
  // Legacy single-provider config (backward compatible)
  llm_provider: string;
  deep_think_llm: string;
  quick_think_llm: string;
  api_key: string;
  llm_proxy_url: string;
}

export const PROVIDERS: [string, string][] = [
  ["openai", "OpenAI"],
  ["anthropic", "Anthropic"],
  ["google", "Google Gemini"],
  ["xai", "xAI Grok"],
  ["deepseek", "DeepSeek"],
  ["qwen", "通义千问 (国际)"],
  ["qwen-cn", "通义千问 (国内)"],
  ["glm", "智谱 GLM (国际)"],
  ["glm-cn", "智谱 GLM (国内)"],
  ["minimax", "MiniMax (全球)"],
  ["minimax-cn", "MiniMax (国内)"],
  ["ollama", "Ollama (本地)"],
  ["openai_compatible", "OpenAI 兼容"],
  ["mistral", "Mistral"],
  ["kimi", "Moonshot (Kimi)"],
  ["groq", "Groq"],
  ["nvidia", "NVIDIA NIM"],
  ["bedrock", "AWS Bedrock"],
];

export const LANGUAGES = [
  "Chinese",
  "English",
  "Japanese",
  "Korean",
  "Spanish",
  "Portuguese",
  "French",
  "German",
  "Arabic",
  "Russian",
  "Hindi",
];

export const DEPTH_OPTIONS: [string, string][] = [
  ["shallow", "浅度 (1轮辩论)"],
  ["medium", "中度 (3轮辩论)"],
  ["deep", "深度 (5轮辩论)"],
];

export const ANALYST_OPTIONS: [string, string][] = [
  ["market", "Market Analyst"],
  ["social", "Sentiment Analyst"],
  ["news", "News Analyst"],
  ["fundamentals", "Fundamentals Analyst"],
];

/** Get the latest trading date (skip weekends, default to Friday for weekends) */
export function latestTradingDate(): string {
  const d = new Date();
  const day = d.getDay(); // 0=Sun, 6=Sat
  if (day === 0) d.setDate(d.getDate() - 2); // Sunday → Friday
  else if (day === 6) d.setDate(d.getDate() - 1); // Saturday → Friday
  // Use local timezone, not UTC (toISOString() would shift by timezone offset)
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

export const DEFAULT_CONFIG: AnalysisConfig = {
  ticker: "AAPL",
  date: latestTradingDate(),
  language: "Chinese",
  analysts: ["market", "social", "news", "fundamentals"],
  depth: "medium",
  // Multi-platform LLM config
  llm_platforms: [],
  quick_model: { platform_id: "", model: "" },
  deep_model: { platform_id: "", model: "" },
  // Legacy single-provider config
  llm_provider: "anthropic",
  deep_think_llm: "claude-sonnet-4-20250514",
  quick_think_llm: "claude-sonnet-4-20250514",
  api_key: "",
  llm_proxy_url: "",
};

// ── Config persistence (localStorage) ──────────────────────────────────────────

const CONFIG_KEY = "tradingagents_config";

export function loadConfig(): AnalysisConfig {
  try {
    const raw = localStorage.getItem(CONFIG_KEY);
    if (!raw) return DEFAULT_CONFIG;
    const parsed = JSON.parse(raw);
    // Always use today's date, ignore any stored date
    return { ...DEFAULT_CONFIG, ...parsed, date: latestTradingDate() };
  } catch {
    return DEFAULT_CONFIG;
  }
}

export function saveConfig(config: AnalysisConfig) {
  try {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
  } catch (e) {
    console.error("Failed to save config:", e);
  }
}

// ── Provider default models ────────────────────────────────────────────────────

export function defaultModelsForProvider(provider: string): [string, string] {
  switch (provider) {
    case "google":
      return ["gemini-3.5-flash", "gemini-3.1-pro-preview"];
    case "openai":
      return ["gpt-5.4-mini", "gpt-5.5"];
    case "anthropic":
      return ["claude-sonnet-4-20250514", "claude-opus-4-20250514"];
    case "xai":
      return ["grok-4.3", "grok-4.3"];
    case "deepseek":
      return ["deepseek-v4-flash", "deepseek-v4-pro"];
    case "ollama":
      return ["qwen3:latest", "glm-4.7-flash:latest"];
    default:
      return ["custom", "custom"];
  }
}

export function apiKeyEnvForProvider(provider: string): string | null {
  const map: Record<string, string> = {
    openai: "OPENAI_API_KEY",
    anthropic: "ANTHROPIC_API_KEY",
    google: "GOOGLE_API_KEY",
    xai: "XAI_API_KEY",
    deepseek: "DEEPSEEK_API_KEY",
    qwen: "DASHSCOPE_API_KEY",
    "qwen-cn": "DASHSCOPE_CN_API_KEY",
    glm: "ZHIPU_API_KEY",
    "glm-cn": "ZHIPU_CN_API_KEY",
    minimax: "MINIMAX_API_KEY",
    "minimax-cn": "MINIMAX_CN_API_KEY",
    mistral: "MISTRAL_API_KEY",
    kimi: "MOONSHOT_API_KEY",
    groq: "GROQ_API_KEY",
    nvidia: "NVIDIA_API_KEY",
  };
  return map[provider] ?? null;
}

// ---------------------------------------------------------------------------
// Ticker history (localStorage)
// ---------------------------------------------------------------------------

const TICKER_HISTORY_KEY = "tradingagents_ticker_history";
const TICKER_HISTORY_MAX = 20;

export function getTickerHistory(): string[] {
  try {
    const raw = localStorage.getItem(TICKER_HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function addTickerToHistory(ticker: string) {
  const upper = ticker.toUpperCase().trim();
  if (!upper) return;
  const history = getTickerHistory().filter((t) => t !== upper);
  history.unshift(upper);
  if (history.length > TICKER_HISTORY_MAX) history.length = TICKER_HISTORY_MAX;
  localStorage.setItem(TICKER_HISTORY_KEY, JSON.stringify(history));
}
