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
  resume?: boolean;
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

// ── Backtest types (mirrors tradingagents_api/routers/backtest.py) ───────────

/** One point on the backtest equity curve. */
export interface EquityPoint {
  date: string;   // YYYY-MM-DD
  value: number;  // account equity
}

/** POST /api/backtest response. */
export interface BacktestResponse {
  ticker: string;
  decision: string;
  total_return: number | null;
  annual_return: number | null;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  total_trades: number;
  profit_trades: number;
  loss_trades: number;
  initial_cash: number;
  final_value: number | null;
  holding_days: number;
  equity_curve: EquityPoint[];
  report_path?: string | null;
  report_markdown?: string | null;
}

/** POST /api/backtest request. */
export interface BacktestRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  decision: string;
  holding_days: number;
  initial_cash?: number;
}

// ── Chart export types (mirrors tradingagents_api/routers/chart_export.py) ──

/** POST /api/chart-export request. */
export interface ChartExportRequest {
  ticker: string;
  date: string;
  days?: number;
  interval?: string | null;
  overlays?: string[];
  ma_params?: Record<string, number>;
  width?: number;
  height?: number;
  dpi?: number;
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

/** Realtime quote for a single ticker (watchlist polling). */
export interface RealtimePrice {
  price: number;
  change: number;
  changePct: number;
  name?: string | null;
  // 五档盘口 (order book)
  bid1_price?: number;
  bid1_vol?: number;
  bid2_price?: number;
  bid2_vol?: number;
  bid3_price?: number;
  bid3_vol?: number;
  bid4_price?: number;
  bid4_vol?: number;
  bid5_price?: number;
  bid5_vol?: number;
  ask1_price?: number;
  ask1_vol?: number;
  ask2_price?: number;
  ask2_vol?: number;
  ask3_price?: number;
  ask3_vol?: number;
  ask4_price?: number;
  ask4_vol?: number;
  ask5_price?: number;
  ask5_vol?: number;
  // 关键指标
  volume?: number;
  outer_disc?: number;
  inner_disc?: number;
  turnover_pct?: number;
  pe_ttm?: number;
  pb?: number;
  mcap_yi?: number;
  float_mcap_yi?: number;
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

/** Get today's date in YYYY-MM-DD format (local timezone) */
export function latestTradingDate(): string {
  const d = new Date();
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
  llm_provider: "google",
  deep_think_llm: "gemini-3.1-pro-preview",
  quick_think_llm: "gemini-3.5-flash",
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

// ── A-stock data center types (Phase 5) ─────────────────────────────────────

export interface AstockFeatureEnvelope<T = Record<string, unknown>> {
  feature: string;
  ticker: string;
  date: string;
  data: T;
  raw_md: string;
}

export interface PriceLevelChip {
  price: number;
  ratio: number;
  is_peak: boolean;
}

export interface ChipDistributionData {
  price_levels: PriceLevelChip[];
  current_price?: number | null;
  profit_ratio?: number | null;
  avg_cost?: number | null;
  peak_price?: number | null;
}

export interface DragonTigerSeat {
  name: string;
  side: "buy" | "sell";
  buy_wan: number;
  sell_wan: number;
  net_wan: number;
  is_institution: boolean;
}

export interface DragonTigerAppearance {
  date: string;
  reason: string;
  net_buy_wan: number;
  turnover_rate?: number | null;
}

export interface DragonTigerData {
  appearances: DragonTigerAppearance[];
  buy_seats: DragonTigerSeat[];
  sell_seats: DragonTigerSeat[];
  inst_buy_wan?: number | null;
  inst_sell_wan?: number | null;
}

export interface NorthboundDay {
  date: string;
  hgt: number;
  sgt: number;
}

export interface NorthboundData {
  hgt_net_inflow?: number | null;
  sgt_net_inflow?: number | null;
  history: NorthboundDay[];
}

export interface ConceptBlockItem {
  name: string;
  category: string;     // '行业' | '概念' | '地域'
  change_pct?: number | null;
  note?: string | null;
}

export interface ConceptBlocksData {
  blocks: ConceptBlockItem[];
  concepts: string[];
}

export interface ProfitForecastYear {
  year: string;
  mean_eps?: number | null;
  min_eps?: number | null;
  max_eps?: number | null;
  analysts?: number | null;
}

export interface ProfitForecastData {
  years: ProfitForecastYear[];
  current_price?: number | null;
  pe_ttm?: number | null;
  forward_pe?: number | null;
  peg?: number | null;
}

export interface LockupBatch {
  date: string;
  shares_type: string;
  quantity?: number | null;
  ratio?: number | null;
}

export interface LockupExpiryData {
  batches: LockupBatch[];
  future_batches: LockupBatch[];
  has_future: boolean;
}

/** Structured financial statement data (balance_sheet / income_statement / cashflow). */
export interface FinancialStatementData {
  periods: string[];                        // ["2026-06-30", "2026-03-31", ...]
  columns: string[];                        // ["资产合计", "负债合计", ...]
  items: Record<string, (number | null)[]>; // column → per-period values
}

/** One row in the industry comparison ranking table. */
export interface IndustryRanking {
  rank: number;
  name: string;
  change_pct: number | null;
  up_count: number | null;
  down_count: number | null;
  leader: string;
}

export interface IndustryComparisonData {
  rankings: IndustryRanking[];
}

/** A parsed section from mootdx F10 shareholder research text. */
export interface InsiderSection {
  title: string;
  content: string;
}

export interface InsiderTransactionsData {
  sections: InsiderSection[];
  raw_text: string;
}

/** All known feature keys — used for tabs, dispatch, and availability checks. */
export type AstockFeatureKey =
  | "chip_distribution"
  | "dragon_tiger"
  | "northbound_flow"
  | "concept_blocks"
  | "profit_forecast"
  | "lockup_expiry"
  | "industry_comparison"
  | "hot_stocks"
  | "insider_transactions"
  | "balance_sheet"
  | "cashflow"
  | "income_statement"
  | "ipo_declaration"
  | "ipo_listing"
  | "margin_detail"
  | "margin_market_stat"
  | "margin_industry"
  | "investment_calendar"
  | "seat_activity"
  | "stock_activity"
  // Phase 9
  | "insider_change_chart"
  | "block_trade_detail"
  | "block_trade_industry"
  | "block_trade_market_stat"
  | "dividend_bonus"
  | "earnings_forecast"
  | "earnings_express"
  | "analyst_rating"
  | "consensus_estimate"
  | "institutional_hold"
  // Phase 12.02: 持仓股东（东财 datacenter/F10，个股级）
  | "holder_num"
  | "free_holders"
  | "holder_increase"
  // Phase 12.04: 公司公告（东财 np-anotice，个股级）
  | "stock_notices"
  // Phase 12.05: 研报流（东财 reportapi，个股级）
  | "research_reports"
  // TongDaXin reference data
  | "survey_interaction"
  | "company_name_changes"
  | "st_changes"
  | "neeq_abnormal_trade"
  | "hk_ipo"
  | "us_ipo"
  | "futures_position"
  | "market_statistics"
  // Phase 10: TongDaXin 数据菜单新模块
  | "fund_purchase"
  | "fund_announcement"
  | "fund_scale"
  | "fund_open_info"
  | "industry_chain_categories"
  | "industry_chain_chains"
  | "industry_list"
  | "industry_detail"
  | "industry_commodity"
  | "macro_gdp"
  | "macro_cpi"
  | "macro_pmi";

export interface AstockFeatureTab {
  key: AstockFeatureKey;
  label: string;
  needsAStock: boolean; // only available for 6-digit codes
}

export const ASTOCK_FEATURE_TABS: AstockFeatureTab[] = [
  { key: "chip_distribution",  label: "筹码分布",  needsAStock: true },
  { key: "dragon_tiger",       label: "龙虎榜",    needsAStock: true },
  { key: "northbound_flow",    label: "北向资金",  needsAStock: false },
  { key: "concept_blocks",     label: "概念板块",  needsAStock: true },
  { key: "profit_forecast",    label: "盈利预测",  needsAStock: true },
  { key: "lockup_expiry",      label: "解禁日历",  needsAStock: true },
  { key: "industry_comparison", label: "行业对比",  needsAStock: true },
  { key: "hot_stocks",         label: "人气榜",    needsAStock: false },
  { key: "insider_transactions", label: "股东动向", needsAStock: true },
  { key: "balance_sheet",      label: "资产负债表", needsAStock: true },
  { key: "cashflow",           label: "现金流量表", needsAStock: true },
  { key: "income_statement",   label: "利润表",    needsAStock: true },
  // Phase 9: 结构化面板（工单 07 — 与后端 FEATURE_TABLE 对齐，key 集必须一致）
  { key: "block_trade_detail", label: "大宗交易",  needsAStock: false },
  { key: "dividend_bonus",     label: "分红送转",  needsAStock: false },
  { key: "earnings_forecast",  label: "业绩预告",  needsAStock: false },
  { key: "analyst_rating",     label: "机构评级",  needsAStock: false },
  { key: "institutional_hold", label: "机构持股",  needsAStock: false },
  // Phase 12.02: 持仓股东（东财 datacenter/F10，个股级）
  { key: "holder_num",         label: "股东户数",  needsAStock: true },
  { key: "free_holders",       label: "十大流通",  needsAStock: true },
  { key: "holder_increase",    label: "增减持",    needsAStock: true },
  { key: "stock_notices",     label: "公告",      needsAStock: true },
  { key: "research_reports",  label: "研报",      needsAStock: true },
];

// ── Phase 7: IPO / Margin Trading / Investment Calendar types ──────────────

export interface IpoDeclarationItem {
  code: string;
  name: string;
  subscribe_date: string;
  subscribe_code: string;
  price: number | null;
  volume_wan: number | null;
  online_volume_wan: number | null;
  subscribe_limit_wan: number | null;
  pe_ratio: number | null;
  lottery_date: string;
}

export interface IpoDeclarationData {
  items: IpoDeclarationItem[];
  total: number;
}

export interface IpoListingItem {
  code: string;
  name: string;
  listing_date: string;
  price: number | null;
  volume_wan: number | null;
  online_volume_wan: number | null;
  pe_ratio: number | null;
  subscribe_date: string;
  win_rate: number | null;
}

export interface IpoListingData {
  items: IpoListingItem[];
  total: number;
}

export interface MarginDetailItem {
  code: string;
  name: string;
  market: string;
  margin_balance: number;
  margin_buy: number;
  margin_repay: number;
  net_buy: number;
  short_qty: number;
  short_sell: number;
  short_repay: number;
  net_short: number;
  market_cap_ratio: number | null;
}

export interface MarginDetailData {
  items: MarginDetailItem[];
  market: string;
  date: string;
  total: number;
}

export interface MarginStatDay {
  date: string;
  margin_balance: number;
  margin_buy: number;
  short_qty: number;
  short_balance: number;
  total_balance: number;
}

export interface MarginMarketStatData {
  items: MarginStatDay[];
  market: string;
}

export interface MarginIndustryItem {
  industry: string;
  margin_ratio_pct: number;
  short_ratio_pct: number;
}

export interface MarginIndustryData {
  items: MarginIndustryItem[];
  date: string;
}

export interface CalendarEventGroup {
  code: string;
  name: string;
  description?: string;
  suspend_date?: string;
  resume_date?: string;
  reason?: string;
  date?: string;
  quantity_wan?: number;
  ratio_pct?: number;
}

export interface InvestmentCalendarData {
  date: string;
  ipo_listing: CalendarEventGroup[];
  ipo_declaration: CalendarEventGroup[];
  suspension_resumption: CalendarEventGroup[];
  special_treatment: CalendarEventGroup[];
  lockup_expiry: CalendarEventGroup[];
}

export interface SeatActivityItem {
  name: string;
  turnover_wan: number;
  appear_count: number;
  buy_count: number;
  buy_amount_wan: number;
  sell_count: number;
  sell_amount_wan: number;
  net_buy_wan: number;
}

export interface SeatActivityData {
  period: string;
  items: SeatActivityItem[];
}

export interface StockActivityItem {
  code: string;
  name: string;
  last_appear_date: string;
  turnover_wan: number;
  appear_count: number;
  buy_amount_wan: number;
  sell_amount_wan: number;
  net_buy_wan: number;
}

export interface StockActivityData {
  period: string;
  items: StockActivityItem[];
}

// ── Price alert types (ticket 5.08) ────────────────────────────────────────

export interface PriceAlert {
  id: string;
  ticker: string;
  name?: string | null;
  /** Local conditions are "above"/"below"; server conditions
   *  (price_above, indicator_above, cross_above, ...) round-trip
   *  through sync and render as their raw value - never evaluated
   *  locally by the price watcher. */
  condition: "above" | "below" | (string & {});
  target_price: number;
  enabled: boolean;
  triggered?: boolean;   // true once the alert has fired
  created_at: string;    // ISO timestamp
  /** Epoch seconds of the last semantic change - drives newer-wins
   *  merge with the server (ticket #12). */
  updated_at?: number;
}

export const ALERTS_STORAGE_KEY = "tradingagents_price_alerts";

// ── Screener types (Phase 6, ticket 6.02) ──────────────────────────────────

export interface ScreenerFilter {
  field: string;
  operator: string;
  value: unknown;
  period?: string | null;
}

export interface ScreenerCriteria {
  filters: ScreenerFilter[];
  sort_by?: string | null;
  ascending?: boolean;
}

export interface ScreenerResultItem {
  ticker: string;
  name: string;
  price?: number | null;
  change_pct?: number | null;
  pe?: number | null;
  industry?: string | null;
  score: number;
  match_details?: Record<string, unknown>;
}

export interface ScreenerResponse {
  query: string;
  parsed_criteria: ScreenerCriteria;
  results: ScreenerResultItem[];
  count: number;
  suggestion: string;
}

// ── Hot Stocks Panel types ───────────────────────────────────────────────

export interface HotStockItem {
  ticker: string;
  name: string;
  change_pct?: number | null;
  turnover_rate?: number | null;
  volume_wan?: number | null;
  net_flow_wan?: number | null;
  topics?: string;
}

export interface HotStocksData {
  items: HotStockItem[];
  total: number;
}

export interface NorthboundFavoriteItem {
  ticker: string;
  name: string;
  change_pct?: number | null;
  northbound_net_wan?: number | null;
  northbound_days?: number | null;
  industry?: string;
}

export interface DragonTigerActiveItem {
  ticker: string;
  name: string;
  change_pct?: number | null;
  net_buy_wan?: number | null;
  reason?: string;
  appearances?: number;
}

export interface InstitutionalAttentionItem {
  ticker: string;
  name: string;
  change_pct?: number | null;
  analyst_count?: number | null;
  pe_ttm?: number | null;
  peg?: number | null;
}

export interface HotStocksPanelResponse {
  date: string;
  attention: HotStockItem[];
  northbound: NorthboundFavoriteItem[];
  dragon_tiger: DragonTigerActiveItem[];
  institutional: InstitutionalAttentionItem[];
}

// ── Portfolio types (Phase 6, ticket 6.04) ──────────────────────────────────

export interface PortfolioPosition {
  ticker: string;
  name: string;
  quantity: number;
  avg_cost: number;
  current_price?: number | null;
  market_value: number;
  pnl: number;
  pnl_pct: number;
}

export interface PortfolioResponse {
  positions: PortfolioPosition[];
  cash: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
}

export interface TradeRecord {
  id: string;
  ticker: string;
  name: string;
  action: "buy" | "sell";
  quantity: number;
  price: number;
  total: number;
  reason: string;
  timestamp: string;
}

export interface NavPoint {
  date: string;
  nav: number;
}

export interface Goal {
  id: string;
  name: string;
  target_value: number;
  current_value: number;
  unit: string;
  deadline: string;
  created_at: string;
}

// ── Market Overview (Phase 8) ──────────────────────────────────────────────

export interface IndexTrend {
  time: string;
  price: number;
  avg_price: number;
  volume: number;
}

export interface IndexData {
  name: string;
  price: number;
  pre_close: number;
  change_pct: number;
  trends: IndexTrend[];
}

export interface StockRankingItem {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  change: number;
  volume: number;
  amount: number;
}

export interface BoardRankingItem {
  code: string;
  name: string;
  change_pct: number;
  price: number;
  change: number;
  volume_ratio: number;
  up_count: number;
  down_count: number;
  limit_up_count: number;
}

export type BoardType = "industry" | "concept" | "style" | "region";

export interface MarketBreadth {
  total: number;
  up_count: number;
  down_count: number;
  flat_count: number;
  total_amount_yi: number;
}

export interface MarketNewsItem {
  title: string;
  content: string;
  time: string;
  source: string;
}

export interface MarketOverviewData {
  timestamp: string;
  indices: Record<string, IndexData>;
  sh_gainers: StockRankingItem[];
  sh_losers: StockRankingItem[];
  sz_gainers: StockRankingItem[];
  sz_losers: StockRankingItem[];
  boards: Record<string, BoardRankingItem[]>;
  breadth: MarketBreadth;
  news: MarketNewsItem[];
}

// ── Phase 10: TongDaXin 数据菜单新模块 ──────────────────────────────────

export interface FundPurchaseItem {
  code: string;
  name: string;
  type: string;
  nav: number | string | null;
  nav_date: string;
  subscribe_status: string;
  redeem_status: string;
  next_open: string;
  min_buy: number;
  daily_limit: number;
  fee_rate: number;
}

export interface FundPurchaseData {
  total: number;
  all: FundPurchaseItem[];
  issuing: FundPurchaseItem[];
  upcoming: FundPurchaseItem[];
  items: FundPurchaseItem[];
  timestamp: string;
}

export interface IndustryChainCategory {
  [key: string]: string[];
}

export interface ChainCard {
  name: string;
  change_pct: number;
  has_data: boolean;
}

export interface IndustryChainData {
  categories: {
    categories: IndustryChainCategory;
    count: number;
    timestamp: string;
  };
  chains: {
    hot: ChainCard[];
    new: ChainCard[];
    all: ChainCard[];
    timestamp: string;
  };
  timestamp?: string;
}

export interface IndustryDataList {
  categories: string[];
  industries: any[];
  total: number;
  timestamp: string;
}

export interface CommodityData {
  name: string;
  unit: string;
  price: number;
  change: number;
  change_pct: number;
  history: { date: string; price: number; change: number; change_pct: number }[];
}

export interface IndustryDataOverview {
  list: IndustryDataList;
  commodity: {
    commodities: CommodityData[];
    timestamp: string;
  };
  default_detail?: any;
}

export interface MacroGdpData {
  trend: { quarter: string; gdp: number; primary: number; secondary: number; tertiary: number }[];
  growth: { quarter: string; gdp_growth: number }[];
  structure: { quarter: string; primary_pct: number; secondary_pct: number; tertiary_pct: number }[];
  timestamp: string;
}

export interface MacroAnalysisData {
  gdp: MacroGdpData;
  cpi: { monthly: any[]; yearly: any[]; timestamp: string };
  pmi: { data: any[]; timestamp: string };
  categories: { categories: string[]; available: string[]; timestamp: string };
}

// ── Unified feature payload contract (ticket 02) ────────────────────────────
// Mirror of tradingagents_api/feature_payload.py. Every structured feature
// returns this envelope so one generic table renders them all.
// `kind: "raw"` is the EXPLICIT degradation path (carries markdown); it is
// tech debt, never the silent default.

export type FeatureUnit =
  | "元"
  | "万元"
  | "亿元"
  | "percent"
  | "股"
  | "万股"
  | "亿股"
  | "ratio"
  | "count"
  | "date"
  | "text";

export type FeatureFormat =
  | "int"
  | "float2"
  | "float4"
  | "date"
  | "text"
  | "signed";

export interface FeatureColumn {
  key: string;
  label: string;
  unit?: FeatureUnit;
  format?: FeatureFormat;
}

export interface FeatureProvenance {
  source?: string;
  as_of?: string;
  ttl_hint?: number | null;
}

export interface FeaturePayloadEnvelope {
  kind: "table" | "raw";
  columns: FeatureColumn[];
  rows: Record<string, unknown>[];
  provenance?: FeatureProvenance;
  raw_md?: string;
}

/** Columns carry unit + format hints; the renderer must not infer them. */
export function formatFeatureCell(
  value: unknown,
  column: FeatureColumn,
): string {
  if (value === null || value === undefined || value === "") return "—";
  if (column.unit === "date" || column.format === "date") return String(value);

  if (typeof value === "number") {
    const digits = column.format === "float4" ? 4 : column.format === "float2" ? 2 : 0;
    let text = value.toFixed(digits);
    if (column.format === "signed" && value > 0) text = `+${text}`;
    if (column.unit === "percent") text = `${text}%`;
    return text;
  }
  return String(value);
}
