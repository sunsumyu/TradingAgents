# TradingAgents 开发文档

> **文档定位**：面向开发者的完整技术内幕——环境搭建、数据流、模块实现机制、扩展指南、测试与踩坑。
> 配套文档：功能视角见 [`FEATURES.md`](FEATURES.md)；模块设计原则见 [`specs/2026-08-29-tdx-style-platform-design.md`](specs/2026-08-29-tdx-style-platform-design.md)。
>
> 本文所有内容基于 2026-08-29 代码库实际实现核实，非设计稿照抄。

---

## 目录

1. [开发环境搭建](#1-开发环境搭建)
2. [代码库结构总览](#2-代码库结构总览)
3. [核心数据流](#3-核心数据流)
4. [后端模块详解](#4-后端模块详解)
5. [前端架构](#5-前端架构)
6. [配置参考](#6-配置参考)
7. [扩展指南（How-to）](#7-扩展指南how-to)
8. [测试指南](#8-测试指南)
9. [已知坑与调试经验](#9-已知坑与调试经验)
10. [发布与打包](#10-发布与打包)

---

## 1. 开发环境搭建

### 1.1 前置要求

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 后端全部逻辑 |
| Node.js | 18+ | 前端构建（Vite 5 + React 18 + TS 5.6） |
| Rust toolchain | stable | 仅打包 Tauri 桌面壳时需要（`cargo`） |
| akshare / akquant | 可选 | A股数据源 / 回测引擎（可选依赖） |

### 1.2 安装

```bash
# 克隆后可编辑安装（按需选 extras）
pip install -e ".[gui,dev]"            # 基础 + API 服务 + 测试工具
pip install -e ".[astock]"             # + akshare A股数据源
pip install -e ".[backtest]"           # + akquant 回测（含 polars/pyarrow/plotly）
pip install -e ".[bedrock]"            # + langchain-aws

cd tradingagents_gui && npm install    # 前端依赖
```

### 1.3 启动

```bash
# 方式一：一键启动（后端 granian + Tauri 桌面壳）
python start_gui.py
# BACKEND_PORT=8420, BACKEND_HOST=127.0.0.1
# 会查找 tradingagents_gui/target/release/tradingagents-gui.exe 并拉起

# 方式二：分别启动（日常开发推荐）
granian tradingagents_api.server:app --interface asgi --host 127.0.0.1 --port 8420
# 或带热重载： python -m tradingagents_api.server   （uvicorn, 0.0.0.0:8000, reload）

cd tradingagents_gui && npm run dev     # Vite → http://localhost:5173
```

> **注意**：前端 `BASE_URL` 硬编码为 `http://127.0.0.1:8420`（`src/lib/api.ts:17`），无环境变量覆盖。改端口需同时改这里。Tauri 壳**不会**自动拉起 Python 后端——连接失败时 GUI 会提示运行 `python start_gui.py`。

### 1.4 Tauri 桌面打包

```bash
cd tradingagents_gui
npm run tauri build    # 产物: target/release/tradingagents-gui.exe
npm run tauri dev      # 调试模式（devUrl 指向 Vite 5173）
```

Tauri 配置要点（`src-tauri/tauri.conf.json`）：identifier `com.tradingagents.app`，窗口 1100×760（最小 820×600），devUrl `http://localhost:5173`，frontendDist `../dist`，CSP 为 null。Rust 侧仅 12 行样板代码（注册 dialog/fs/notification 插件），无自定义 Rust 逻辑、无 sidecar。

### 1.5 运行测试

```bash
python -m pytest                        # 全量 1025+ 用例（约 3 分钟）
python -m pytest tests/test_chart_engine.py -v
cd tradingagents_gui && npm test        # 前端 vitest
```

---

## 2. 代码库结构总览

```
TradingAgents/
├── tradingagents/                    # 核心 Python 包
│   ├── default_config.py             #   DEFAULT_CONFIG + TRADINGAGENTS_* 环境变量映射
│   ├── graph/                        #   多智能体图（trading_graph / setup / checkpointer / llm_client_manager）
│   ├── agents/                       #   智能体（analysts/ researchers/ managers/ risk_mgmt/ trader/ utils/）
│   ├── llm_clients/                  #   LLM 客户端层（factory / openai_client 注册表 / capabilities / catalog）
│   ├── llm_cache.py                  #   LLM 响应缓存（每标的 SQLite）
│   ├── data_cache.py                 #   数据缓存（每标的 SQLite，cached_fetch）
│   ├── api_callbacks.py              #   ProgressCallbackHandler（LangChain 回调 → 进度事件）
│   ├── dataflows/                    #   数据源层（interface 路由 + a_stock/ + y_finance + akshare_vendor …）
│   ├── chart_engine/                 #   引擎①：K线/指标/画线/复盘（25 指标、15 画线、13 周期）
│   ├── data_center/                  #   引擎②：统一数据访问 + SQLite 缓存
│   ├── signal_engine/                #   引擎③：信号/策略/预警
│   ├── screener_engine/              #   引擎④：选股（50 字段、10 模板）
│   ├── portfolio_engine/             #   引擎⑤：组合/绩效
│   ├── backtesting/                  #   akquant 回测封装（engine/strategy/report）
│   └── markets/                      #   市场类型检测（detector）
├── tradingagents_api/                # FastAPI 服务层
│   ├── server.py                     #   app 装配（CORS + 11 个 router）
│   ├── runner/                       #   分析任务生命周期（task_state/config_builder/graph_runner/progress/report_builder）
│   ├── chart_data/                   #   图表数据管线（fetchers/computors/parsers）
│   ├── astock_features.py            #   A股特色功能 FEATURE_TABLE（13 项分发）
│   ├── screener.py / portfolio.py    #   选股/组合 HTTP 服务层（独立实现，见 §4.7）
│   ├── market_data.py                #   分析前市场数据包
│   ├── schemas.py                    #   全部 Pydantic 模型
│   └── routers/                      #   analysis/ market/ astock/ backtest/ screener/ portfolio/ realtime/ providers/ config/ cache/ health
├── tradingagents_gui/                # 前端（React 18 + Zustand + ECharts 6 + Tauri 2）
│   ├── src/App.tsx                   #   阶段状态机（无路由库）
│   ├── src/stores/                   #   全局 store（analysis / config / marketData）
│   ├── src/lib/                      #   api.ts / 图表域 store / 实时行情 hook / 预警 hook / html-export
│   ├── src/components/               #   ConfigPanel / ProgressPanel / ReportPanel / charts/ / tradingview/ / astock/ / screener/ / portfolio/
│   └── src-tauri/                    #   Tauri 2 壳（样板代码）
├── tests/                            # pytest 套件（1025+ 用例）
└── docs/                             # 本文档 + FEATURES.md + specs/
```

---

## 3. 核心数据流

### 3.1 多智能体分析流水线（最重要路径）

```
GUI ConfigPanel
  │ POST /api/analyze (AnalyzeRequest: ticker/date/analysts/depth/quick_model/deep_model)
  ▼
runner.start_analysis()
  ├─ 生成 uuid4 task_id，创建 TaskState（内存注册表 _tasks + 锁）
  ├─ 立即返回 {task_id, status:"started"}
  └─ 启动守护线程 analysis-{task_id[:8]} → _run_analysis()
       │
       ├─ build_config(request)         # depth→轮数 {shallow:1, medium:3, deep:5}
       ├─ setup_provider_env()          # provider→环境变量注入（_API_KEY_MAP，15 个提供商）
       ├─ ProgressCallbackHandler 接线  # set_event_sink / set_token_sink / set_error_callback
       ├─ TradingAgentsGraph(selected_analysts, config) 构建
       ├─ A股特化: detect_market_type → 强制 a_stock vendor + 中文输出 + 追加 3 个A股分析师 → 重建图
       ├─ Checkpoint: get_checkpointer(每标的 SqliteSaver) → checkpoint_step（resume 或清除断点）
       ├─ 超时: max(30, 分析师数×6 + (辩论+风险)×2 + 5) 分钟，守护线程计时
       ├─ 心跳: 每 15s 发 "⏳ {agent} 正在处理中… (Ns)"
       │
       ├─ graph.graph.stream(init_state) 逐块消费：
       │    ├─ detect_progress(chunk) → TaskState.add_event（agent:status 去重）
       │    ├─ 回调 on_chat_model_stream → task.add_token（token 级流式）
       │    └─ 重试: 429 → 退避 30/60/120s（最多3次）；网络抖动 → 5s（最多2次）
       │
       └─ 完成: process_signal(final_trade_decision) → build_report() → task.set_completed()
            失败: task.set_error(err) ；成功后清除断点

GUI（并行）
  └─ GET /api/analyze/{task_id}/stream  (SSE, 轮询 TaskState 每 0.5s)
       ├─ event: progress  {phase, agent, status, message}
       ├─ event: token     {agent, token}
       ├─ event: complete  {ticker, signal}
       └─ event: error     {message}
```

**TaskState 关键机制**：事件按 `"agent:status"` 键去重（每个智能体每种状态只发一次）；token 缓冲由 SSE 端 `flush_tokens()` 排空；事件数组内存中保留最近 200 条（`slice(-199)`）；GUI 报告轮询 240 次 × 5s（20 分钟兜底超时）。

### 3.2 Agent 图内部流程

```
START
 → 分析师串行（每个: agent节点 ⇄ ToolNode 工具循环 → create_msg_delete 清理消息 → 下一个）
   [market / social / news / fundamentals] + A股追加 [policy / hot_money / lockup]
 → Bull Researcher ⇄ Bear Researcher（should_continue_debate, max_debate_rounds 轮）
 → Research Manager（deep LLM，结构化 investment_plan）
 → Trader（quick LLM → trader_investment_plan）
 → Aggressive / Conservative / Neutral 风险辩论（max_risk_discuss_rounds 轮）
 → Portfolio Manager（deep LLM）→ final_trade_decision ★
 → END
```

- 图形状由 `setup_graph(selected_analysts)` 动态组装：只添加被选分析师的 `AnalystNodeSpec`（agent_node/tool_node/clear_node 三元组）。
- **final_trade_decision 由 Portfolio Manager 节点产出**，为结构化 `PortfolioDecision`（Pydantic）+ Markdown 渲染。
- 递归上限 = `max(max_recur_limit=100, compute_recursion_limit(分析师数, 辩论轮数, 风险轮数))`。
- `TradingAgentsGraph` 本体是薄编排层，逻辑拆在 `llm_client_manager / returns_resolver / memory_orchestrator / report_writer / state_logger / graph_variant_cache` 六个协作模块。

### 3.3 图表数据流水线

```
POST /api/chart-data {ticker, date, days=90, interval?}
  ├─ 分钟线 (interval∈{1m,5m,15m,30m,60m}):
  │    A股 → mootdx TDX TCP（240根/页分页，上限800根，频率码 {1m:8, 5m:0, 15m:1, 30m:2, 60m:3}）
  │    全球 → yfinance（周期上限 1m:7d … 60m:730d）
  │    → 只返回 ChartData(kline, dashboard)
  └─ 日线:
       _fetch_ohlcv → cached_fetch(每标的SQLite, TTL 24h)
         A股: dataflows.a_stock.get_stock_data（mootdx→新浪回退）优先，失败 route_to_vendor
       → parse_ohlcv_csv（多源列名兼容）→ KlineData（MA5/10/20/50、EMA12/26、KDJ 本地计算）
       → 指标并行抓取 ThreadPoolExecutor(7): macd/macds/macdh/rsi/boll/boll_ub/boll_lb
       → Dashboard: 评级(Buy…Sell 五档) + 置信度(low30/medium60/high85) + 四维评分(关键词计数, 各满分10)
       → 资金流(仅A股): get_fund_flow + get_northbound_flow 合并（主力=main，散户=small+mid）
```

前端拿到 K线后，**MA/MACD/RSI 在浏览器端用 `useMemo` 从 closes 重算**——调整指标参数不触发重新请求。

### 3.4 实时行情流水线

```
前端 useRealtimePrices(tickers)
  ├─ 优先: WebSocket ws://127.0.0.1:8420/ws/realtime（服务端 ~3s 推送，断线 5s 重连）
  └─ 回退: HTTP POST /api/realtime-prices 轮询（每 5s）
后端: A股 → 腾讯批量行情接口；全球 → yfinance（单只）
```

---

## 4. 后端模块详解

### 4.1 LLM 客户端体系（`tradingagents/llm_clients/`）

**分层**：`BaseLLMClient`(ABC) → 各原生 API 客户端 → 一个注册表驱动的 `OpenAIClient` 覆盖全部 OpenAI 兼容家族。`factory.py` 按提供商名解析。

| 文件 | 职责 |
|------|------|
| `base_client.py` | 抽象基类：`get_llm()` / `validate_model()`；模块级 `normalize_content`（扁平化 blocks 内容）、`warn_if_truncated`（max_tokens 截断检测） |
| `factory.py` | `create_llm_client(provider, …)` 分发 + `create_quick_llm(config)` / `create_deep_llm(config)`（读 `quick_llm_provider`/`deep_llm_provider`，回退 `llm_provider`） |
| `openai_client.py` | 最大文件（351 行）：`NormalizedChatOpenAI` 基类、`DeepSeekChatOpenAI`（reasoning_content 往返）、`MinimaxChatOpenAI`（reasoning_split）、`LocalCompatibleChatOpenAI`（vLLM/LM Studio）、`ProviderSpec` 冻结数据类注册表、`OpenAIClient` |
| `anthropic_client.py` | `effort` 参数仅对支持的模型传递（opus≥4.5 / sonnet≥4.6 / fable≥5.0 正则）；默认 `streaming=False`（代理分块读取可靠性） |
| `capabilities.py` | 每模型能力声明表：`supports_tool_choice` / `requires_reasoning_content_roundtrip`（DeepSeek thinking）/ `requires_reasoning_split`（MiniMax M2.x） |
| `model_catalog.py` | `MODEL_OPTIONS`: provider → {quick[], deep[]} 模型目录（10+ 提供商），`get_known_models()` 供校验 |
| `api_key_env.py` | `PROVIDER_API_KEY_ENV`: provider → 环境变量名（见下表） |
| `validators.py` | `validate_model()`；8 个"任意模型"提供商（ollama/openrouter/openai_compatible 等）跳过目录校验 |

**提供商 → API Key 环境变量全表**：

| Provider | 环境变量 | Provider | 环境变量 |
|----------|----------|----------|----------|
| openai | `OPENAI_API_KEY` | minimax | `MINIMAX_API_KEY` |
| anthropic | `ANTHROPIC_API_KEY` | minimax-cn | `MINIMAX_CN_API_KEY` |
| google | `GOOGLE_API_KEY` | openrouter | `OPENROUTER_API_KEY` |
| azure | `AZURE_OPENAI_API_KEY` | mistral | `MISTRAL_API_KEY` |
| bedrock | AWS 凭证链 | kimi | `MOONSHOT_API_KEY` |
| xai | `XAI_API_KEY` | groq | `GROQ_API_KEY` |
| deepseek | `DEEPSEEK_API_KEY` | nvidia | `NVIDIA_API_KEY` |
| qwen | `DASHSCOPE_API_KEY` | ollama | 无需 key |
| qwen-cn | `DASHSCOPE_CN_API_KEY` | openai_compatible | `OPENAI_COMPATIBLE_API_KEY`（可选） |
| glm | `ZHIPU_API_KEY` | glm-cn | `ZHIPU_CN_API_KEY` |

**DeepSeek thinking 模型关键细节**（issue #678）：`supports_tool_choice=False` 时 `with_structured_output(method="function_calling")` 自动置 `tool_choice=None`（schema 仍作为 tool 绑定）；`reasoning_content` 在响应接收时存入 `additional_kwargs`，下次请求时由 `_get_request_payload` 回传——缺失会 400。

**base_url 优先级**（`OpenAIClient.get_llm()`）：`self.base_url` > 环境变量覆盖 > `ProviderSpec` 默认。自定义 `backend_url` 且无 key 时注入 `sk-placeholder` 占位 key；仅当 provider=openai **且** base_url 为官方 `api.openai.com` 时才走 Responses API。

### 4.2 数据源 Vendor 路由（`tradingagents/dataflows/interface.py`）

- **6 大 vendor**：`yfinance` / `fred` / `polymarket` / `alpha_vantage` / `a_stock` / `akshare`。
- **类别 → 方法**：`TOOLS_CATEGORIES` 7 类（core_stock_apis / technical_indicators / fundamental_data / news_data / macro_data / prediction_markets / signal_data），`VENDOR_METHODS` 记录每个方法的 {vendor: 函数} 映射。
- **配置优先级**：`tool_vendors[方法名]` > `data_vendors[类别]` > `"default"`（= 该方法全部可用 vendor）。
- **链式语义（重要）**：显式配置即完整链——**不会**静默回退到用户未选的 vendor（#988/#289 教训）。多源回退写逗号列表如 `"akshare,yfinance"`。仅 429 限流 / 未配置 / 无数据三类异常触发链内下一家。
- **哨兵语义**：全部链耗尽后——若有 `NoMarketDataError` → 返回 `NO_DATA_AVAILABLE: …（禁止编造数值）` 指令文本；若是真实错误 → 抛出（optional 类别 macro/prediction_markets 降级为 `DATA_UNAVAILABLE` 文本，不中断分析）。
- **a_stock 子包内部**：`ohlcv.py`（mootdx TCP → 新浪回退 → CSV 缓存）、`tencent_quote.py`（批量实时）、`chip_distribution.py`（筹码估算）、`northbound_flow.py` 等。

### 4.3 三层缓存体系（互相独立）

| 缓存 | 位置 | 粒度 | 存储 | TTL | 开关 |
|------|------|------|------|-----|------|
| 行情/指标数据 | `data_cache.py` `cached_fetch` | 每标的 | SQLite（`~/.tradingagents/cache/`） | 24h（OHLCV 固定） | `data_cache_enabled=True` |
| LLM 响应 | `llm_cache.py` `LLMCache` | 每标的 | `<cache>/llm_cache/<TICKER>.db`（WAL） | 24h | `llm_cache_enabled=False`（默认关） |
| 图状态断点 | `graph/checkpointer.py` | 每标的 | LangGraph SqliteSaver | 无（成功即清除） | `checkpoint_enabled=False`（API 层强制开） |

**LLM 缓存键**（`cache_utils.compute_cache_key`）：`SHA-256({msgs, model, temp})[:32]`；消息规范化时剥离易变字段（id/usage_metadata 等）、ToolMessage 按 tool_call_id 去重、tool_calls 排序——保证 LangGraph 重放命中。`CachedLLM` 是透明包装器：命中反序列化 AIMessage/ToolMessage 等返回，仅缓存成功结果，`stream()` 绕过缓存；在 `trading_graph.propagate()` 中按需包裹 quick/deep 两个 LLM 并经 `GraphVariantCache` 重编译图，finally 中解除包装并输出命中率统计。

### 4.4 智能体与工具（`tradingagents/agents/`）

- 每个智能体是 `create_<role>(llm)` 工厂 → 返回 `(state) -> dict` 节点函数。
- **分析师**（quick LLM + 工具循环）：market / news / fundamentals / sentiment（`social_media_analyst.py` 已是废弃转发 shim）；A股专属：policy（政策）/ hot_money（游资）/ lockup（解禁）。
- **工具按域拆分**：`utils/core_stock_tools.py`、`fundamental_data_tools.py`、`news_data_tools.py`、`macro_data_tools.py`、`prediction_markets_tools.py`、`signal_data_tools.py`、`technical_indicators_tools.py`；`tool_wiring.ANALYST_TOOLS` 映射分析师 → 工具集 → `ToolNode`。
- **状态**：`AgentState` 携带各分析师 `*_report`、`investment_debate_state`（bull/bear 历史+轮数）、`risk_debate_state`、`investment_plan`、`trader_investment_plan`、`final_trade_decision`。
- `quality_gate.py`（数据质量门）已定义但**未被图引用**——待接入。

### 4.5 API 服务层（`tradingagents_api/`）

- **server.py**（97 行）：纯装配——CORS 全开 + 11 个 router 循环注册，无中间件/静态文件/生命周期钩子。
- **runner 包**职责表见 §3.1；`tradingagents_api/__init__.py` 为空，须显式子模块导入。
- **schemas.py**：30+ Pydantic 模型。关键字段：
  - `AnalyzeRequest`：`analysts` 默认 `[market,social,news,fundamentals]`；`depth` shallow/medium/deep；`quick_model`/`deep_model`（ModelConfig: provider/model/api_key?/backend_url?）与 legacy 单提供商字段并存；`resume` 断点续析开关。
  - `KlineData`：dates + ohlc(四元组) + volumes + ma5/10/20/50 + ema12/26 + kdj_k/d/j。
  - `ChartData`：kline?/macd?/rsi?/bollinger?/dashboard?/fundFlow? 可选组合。
- **已知隐患**：`ConfigSaveRequest` 用了 `dict[str, Any]` 但未导入 `Any`——因 PEP 563 惰性求值暂未爆雷，反序列化重建时会 NameError（见 §9）。

### 4.6 A股特色功能分发（`astock_features.py`）

统一入口 `POST /api/astock-features`，`FEATURE_TABLE` 导入时一次性物化，13 个 feature key → `dataflows.a_stock` 函数 + 参数 + 解析器：

| feature | 数据函数 | 默认参数 | 专属解析器 |
|---------|----------|----------|-----------|
| chip_distribution | get_chip_distribution | days=90 | ✅ 结构化 |
| dragon_tiger | get_dragon_tiger_board | look_back_days=30 | ✅ 结构化 |
| northbound_flow | get_northbound_flow | include_history=True | ✅ 结构化（全市场，忽略 ticker） |
| concept_blocks | get_concept_blocks | — | ✅ 结构化 |
| profit_forecast | get_profit_forecast | — | ✅ 结构化 |
| lockup_expiry | get_lockup_expiry | forward_days=90 | ✅ 结构化 |
| hot_stocks | get_hot_stocks | —（全市场） | ✅ 结构化 |
| industry_comparison / insider_transactions / balance_sheet / cashflow / income_statement | 同名函数 | freq=quarterly 等 | ⚠️ `_passthrough_parser`（raw markdown） |

结果经 `cached_fetch_raw` 缓存；`is_astock_code()` 判定：剥后缀/前缀后恰好 6 位数字。

### 4.7 HTTP 服务层的选股/组合（历史实现，与引擎模块并存 ⚠️）

**重要架构事实**：`tradingagents_api/screener.py` 和 `portfolio.py` 是**自包含的历史实现**，**没有** import `screener_engine` / `portfolio_engine`（两套并存）：

| | API 服务层（现网使用） | 引擎模块（新，见 §4.8） |
|---|---|---|
| 选股 | LLM 解析 NL → 12 个字段过滤；股票池 = 人气榜（最多50只候选）；评分 = 命中条件占比×100 + 数据可用性加分；无状态 | 50 字段 × 10 运算符纯正则/规则；10 模板；`screen_natural` 正则解析 |
| 组合 | JSON 文件持久化 `~/.tradingagents/portfolio.json`；初始资金 100 万；NAV 按日记账；ValueError → HTTP 400 | 内存态（进程内）；佣金模型（万三/最低5元）；绩效全套（Sharpe/回撤/Alpha） |

- **选股 LLM 解析**：`CachedLLM(create_quick_llm(config))` + 中文系统提示词 → 结构化 `ScreenerCriteria`；`ticker_hint`（合法A股代码）跳过发现直接分析单只。
- **组合交易路由**：`POST /api/portfolio/trade` → `execute_trade`（买入现金校验+加权成本；卖出持仓校验+清零删除）。

> **重构方向**：HTTP 层应逐步迁移到底层引擎模块（组合迁移收益最大——获得绩效分析与佣金模型；选股需先统一字段口径）。

### 4.8 五大引擎模块 + 回测（`tradingagents/*_engine/`, `backtesting/`）

深度模块设计：小接口、大实现。全部有独立测试（合计 288 个用例）。

#### chart_engine（K线/指标/画线/复盘，~1370 行）

- `Timeframe`（13 值枚举 + `TIMEFRAME_REGISTRY` + `resolve_timeframe` 中文模糊匹配，含 mootdx 频率码映射）。
- `INDICATOR_LIBRARY`：25 个指标（主图 MA/EMA/BOLL/SAR/ATR；副图 MACD/RSI/KDJ/WR/CCI/DMI/TRIX/DMA/ROC/MTM/BIAS/ASI/EMV/ARBR/CR/DMIADX；量能 VR/OBV/VWAP/MV）。每个是 `IndicatorDef(name, category, params, param_ranges, description)` + 纯函数计算器注册在 `_COMPUTE_FN`。
- `IndicatorComputer.compute/compute_batch/detect_signals`；信号探测器仅 MACD（金叉死叉）/RSI（70/30）/KDJ（低位金叉高位死叉）三组。
- `DrawingManager`：15 种 `DrawingType`；坐标 = (time_index, price) 两元组（随K线缩放联动）；`hit_test(tolerance=5.0)`；`Drawing.to_dict/from_dict` 序列化；斐波那契 7 档位常量 `FIBONACCI_LEVELS` + 工厂函数族（`create_trendline` 等 11 个）。
- `ChartEngine` 门面（renderer.py）：`render / compute_indicator / compute_batch / detect_signals / add_drawing / replay / export_image(占位返回空bytes)`。

#### data_center（数据门面 + 缓存，~730 行）

- `DataCenter.get_ohlcv()`（缓存优先 → `stockstats_utils.load_ohlcv` 回源，qfq）、`get_realtime()`（A股腾讯批量 / 全球 yfinance）、`get_news()`（vendor 路由，上限20条）、`get_fundamental()`、`clear_cache / cache_stats`。
- `CacheManager`：每标的一个 .db（WAL），`ohlcv` + `indicator` 两张表，TTL 惰性过期，容量上限 500MB。

#### signal_engine（信号/策略/预警，~690 行）

- `compute_signals(ticker, timeframe, indicators?)` → `CompositeSignal`：默认 MACD+RSI+KDJ；**权重表** MACD 1.5 / MA 1.3 / RSI·KDJ 1.2 / BOLL·DMI 1.0 / SAR 0.9 / CCI·WR 0.8 / TRIX 0.7；推荐阈值 BUY≥65 / SELL≤35；置信度 = 指标间一致度。
- `run_strategy()`：bar 级模拟（90% 现金买入）、年化 Sharpe(√252)、最大回撤、胜率；规则支持默认 MA5/20 交叉、`ma_cross`、`rsi_threshold`。
- `AlertCondition` 7 种定义、`check_alerts` 实际求值 3 种（price_above/below、volume_above）——见 FEATURES.md §13 差距表。

#### screener_engine（选股，~580 行）

- `SCREEN_FIELDS` 50 字段 × 5 组；`FilterOperator` 10 种（含实现期新增的 `NOT_IN`）。
- `PRESET_TEMPLATES` 10 套（value/growth/momentum/oversold/large_cap/small_cap_growth/dividend/low_pe/high_volatility/northbound）。
- `screen()` 多条件 AND；`screen_natural()` 正则解析（PE/PB/ROE/市值/涨幅/股息/增速/RSI + 7 行业词 + 北向）；默认股票池 = 人气榜 `get_hot_stocks()`。

#### portfolio_engine（组合/绩效，~500 行）

- `execute_trade`（佣金 `max(amount×rate, min_commission)`；加权平均成本；资金/持仓不足抛 ValueError）→ `TradeRecord`（uuid8）。
- `get_positions(current_prices?)` → `PortfolioSummary`（逐仓浮动盈亏 + 权重含现金归一）。
- `get_performance()` → 买卖 FIFO 配对逐笔收益 → 胜率/盈亏比/最佳最差 + NAV 序列 Sharpe(√252)/峰值回撤 + Alpha。
- 全模型带 `to_dict()`。

#### backtesting（akquant 封装，~575 行）

- `BacktestEngine.run()`（通用） / `run_from_decision(final_state)`（解析 `final_trade_decision` 中英文关键词 → BUY/SELL/HOLD → 动态生成 `AgentDecisionStrategy` 子类 → akquant 执行）。
- 数据经 akshare `stock_zh_a_hist`（qfq）；报告落 `results/backtest/{ticker}_{stamp}.md`。
- akquant 未安装时 lazy import 优雅降级（`_get_aq()` 抛带安装指引的 ImportError）。
- `TradingAgentsGraph.backtest()` 是图上的便捷入口。

---

## 5. 前端架构

### 5.1 技术栈与构建

| 层 | 选型 | 说明 |
|----|------|------|
| 框架 | React 18.3（无路由库） | 阶段切换靠 zustand `phase` 字段 |
| 状态 | zustand 5 | 每域一个 store，无 Context/prop 钻孔 |
| 图表 | ECharts 6 + echarts-for-react | 放弃 lightweight-charts（Tauri webview 兼容性，依赖仍在但仅死代码引用） |
| 样式 | tailwindcss 3.4 | |
| Markdown | react-markdown + remark-gfm | 报告渲染 |
| Tauri | 2.x + plugin-dialog/fs/notification | capabilities: 写文件/保存对话框/桌面通知 |
| 构建 | Vite 5 + tsc + vitest | 端口 5173 strict |

### 5.2 状态管理布局

```
src/stores/（全局应用域）
├── useAnalysisStore   # phase, events[](上限200), streamingText/Agent, report, taskId,
│                      # checkpointInfo；拥有 SSE 生命周期 + 报告轮询(240×5s)
├── useConfigStore     # config, backendOnline, backendStatus；健康检查 6次×2s；
│                      # 配置双持久化: localStorage("tradingagents_config") + POST /api/config(后端YAML)
└── useMarketDataStore # 两步工作流的市场数据预览

src/lib/（图表域）
├── useChartStore      # ticker/timeframe/kline/macd/rsi/bollinger/crosshairInfo/
│                      # activeTool/activeOverlays(默认ma5/10/20/50)/replay/isMultiChart（纯内存）
├── useRealtimePrices  # WS优先(3s推送) → HTTP轮询回退(5s)；Map<ticker, RealtimePrice>
├── usePriceAlerts     # React hook：预警CRUD + 1% 迟滞复位 + Tauri 桌面通知；localStorage
└── watchlist-store    # 纯模块函数（非zustand）：自选股分组；localStorage（含旧版扁平key迁移）

localStorage 键：tradingagents_config / _ticker_history / _watchlist_groups / _price_alerts / _multi_layout
```

### 5.3 App 阶段机与页面

`Phase = config | market_data | analyzing | report | error | screener | portfolio`，由 `navigateTo()` 切换；App.tsx **零状态**（只订阅三个 store）；ReportPanel/MarketDataPanel/ScreenerPanel/PortfolioPanel 均 `lazy()+Suspense`，且每个非 config 阶段包一层类组件 ErrorBoundary。`main.tsx` 注入全局 `window.onerror`/`unhandledrejection` 错误浮层（Tauri webview 调试用）。

### 5.4 图表区组合（TradingViewLayout，537 行）

```
ChartHeader（代码/现价/涨跌幅 + AlertPanel 弹层）
├─ 左: DrawingToolbar（15 工具）
├─ 中: TimeframeSelector → ReplayControls → IndicatorBar(+截图/全屏) → TradingViewChart → SubPanels(3插槽)
└─ 右: WatchlistPanel（固定 220px）
```

- **指标参数**是组件局部状态（`loadIndicatorParams/saveIndicatorParams` 持久化），MA/MACD/RSI **前端重算**（useMemo），改参数零网络请求。
- **画线实现**：`DrawingOverlay` 在 ECharts canvas 上叠一层**透明 HTML canvas**（`canvas[data-drawing-canvas]`），crosshair 模式指针事件穿透；支持趋势线/水平线/矩形/斐波那契，50 步撤销栈，切标的经 `resetKey` 重置。⚠️ `DrawingManager.ts`（415 行，lightweight-charts IPanePrimitive 实现）是**死代码**，无引用。
- **多图**：`isMultiChart` 时整体替换为 `MultiChartLayout`（CSS Grid 1×1/1×2/2×2，布局持久化 localStorage），每窗格独立 useState 独立取数，十字光标时间经共享 Context 跨窗格同步。
- **截图导出**：所有 ECharts canvas + 画线 canvas 合成到 2× DPR 离屏 canvas → PNG 下载。
- **离线报告导出**（`html-export.ts`）：`echarts-bundle.ts` 用 Vite `?raw` 懒加载 `echarts.min.js`（~1.1MB code-split chunk）内联进独立 HTML。

### 5.5 i18n

**无 i18n 库**——UI 字符串硬编码中文（混排英文技术词）。多语言需求出现时需先引入 react-i18next 并批量抽词。

---

## 6. 配置参考

### 6.1 DEFAULT_CONFIG 全键（`tradingagents/default_config.py`）

约 25 个 `TRADINGAGENTS_*` 环境变量可覆盖（`_ENV_OVERRIDES` 映射；类型按默认值强转，**非法值启动即报错**，不静默回退）。

| 键 | 默认 | 说明 |
|----|------|------|
| results_dir | `~/.tradingagents/logs` | 报告/日志输出 |
| data_cache_dir | `~/.tradingagents/cache` | SQLite 数据 + 断点存储 |
| memory_log_path | `~/.tradingagents/memory/trading_memory.md` | 反思记忆 |
| llm_provider / deep_think_llm / quick_think_llm | openai / gpt-5.5 / gpt-5.4-mini | 默认 LLM |
| quick_llm_provider / deep_llm_provider | None | 按模型类型分提供商（回退 llm_provider） |
| backend_url（_quick/_deep） | None | 自定义端点；None=各官方端点 |
| google_thinking_level / openai_reasoning_effort / anthropic_effort | None | 各家思考力度参数 |
| temperature / llm_max_retries / max_tokens | None / None / None | None=提供商默认 |
| llm_timeout | 300 | LLM HTTP 超时（秒） |
| checkpoint_enabled | False | 断点续析（API 层强制开） |
| llm_cache_enabled / llm_cache_ttl_hours | False / 24 | LLM 响应缓存 |
| data_cache_enabled / data_cache_ttl_hours | True / 24 | 行情数据缓存 |
| output_language | "English" | 报告语言（内部辩论恒英文） |
| max_debate_rounds / max_risk_discuss_rounds | 1 / 1 | 辩论轮数 |
| max_recur_limit | 100 | LangGraph 递归上限 |
| news_article_limit / global_news_article_limit / global_news_lookback_days | 20 / 10 / 7 | 新闻抓取量 |
| global_news_queries | 5 条宏观查询 | 联储/标普/地缘/央行/大宗 |
| data_vendors | 全 yfinance（macro=fred, pm=polymarket） | 类别级 vendor 链 |
| tool_vendors | {} | 方法级覆盖 |
| benchmark_ticker / benchmark_map | None / 后缀→指数映射 | 反思 Alpha 基准 |
| market_type / astock_lookback_days / astock_trading_sessions | auto / 60 / True | 市场检测与A股窗口 |

**配置运行时机制**（`dataflows/config.py`）：模块级全局单例——`initialize_config()` 深拷贝 DEFAULT_CONFIG；`set_config()` 一层深合并；`get_config()` 返回**深拷贝**（防外部改动泄漏）。进程内有效，不落盘。

### 6.2 GUI 配置链路

前端 `AnalysisConfig`（localStorage）→ `startAnalysis()` 时转换为 `AnalyzeRequest`（多平台 `quick_model`/`deep_model` 优先，legacy 单提供商字段兼容）→ 后端 `build_config` 深拷贝合并。GUI「保存配置」双写：localStorage + `POST /api/config`（后端 YAML）。

---

## 7. 扩展指南（How-to）

### 7.1 新增技术指标（chart_engine）

1. `chart_engine/indicators.py` 写纯函数 `def _compute_xxx(df, period) -> dict[str, list]`（列名规范：close/high/low/volume；除零用 `.replace(0, np.nan)` 或 `1e-10`——RSI 全涨案例的教训）。
2. 注册到 `_COMPUTE_FN` 字典。
3. `INDICATOR_LIBRARY["XXX"] = IndicatorDef(name="XXX", category="oscillator", params={"period": 14}, param_ranges={"period": (2, 60)}, description="…")`。
4. （可选）信号探测器：写 `_detect_xxx_signals(result) -> list[Signal]` 并注册。
5. 测试：`tests/test_chart_engine.py` 加计算正确性 + `available_indicators()` 包含性用例。

### 7.2 新增画线工具

1. `chart_engine/drawings.py` 的 `DrawingType` 枚举加值。
2. 需要专属几何逻辑时写工厂函数（参考 `create_fibonacci` + `compute_fibonacci_levels`）。
3. 前端：`DrawingOverlay.tsx` 加绘制/命中逻辑（透明 canvas 层），`DrawingToolbar` 加按钮。

### 7.3 新增选股字段/模板（screener_engine）

- **字段**：`screener_engine/models.py` 的 `SCREEN_FIELDS` 加条目（分组、中文名、取数函数）；确保股票池数据源能产出该字段。
- **模板**：`engine.py` 的 `PRESET_TEMPLATES` 加 `ScreenerTemplate(id, name, description, category, filters, sort_by, …)`——GUI 模板列表自动出现。

### 7.4 新增数据 Vendor（以 akshare 为模板）

1. 新建 `dataflows/<name>_vendor.py`：**lazy import** 可选依赖（`_get_x()` 失败抛 `VendorNotConfiguredError`）；函数签名对齐 `VENDOR_METHODS` 既有方法；错误包装进 `NoMarketDataError`（关键词匹配"不存在/no data"等）。
2. `interface.py`：import 模块 + `VENDOR_LIST` 加名 + `VENDOR_METHODS` 逐方法注册。
3. `pyproject.toml` 加 optional extra。
4. 测试：注册完整性（每个方法能解析到实现）+ 路由选择 + lazy import 缺失报错（参考 `tests/test_akshare_vendor.py` 12 例）。
5. 注意：**不要**给 `get_global_news` 等无对应能力的方法硬注册（akshare 即因此未注册 global_news）。

### 7.5 新增 LLM 提供商

1. OpenAI 兼容：`openai_client.py` 的 `OPENAI_COMPATIBLE_PROVIDERS` 加 `ProviderSpec(chat_class, base_url, base_url_env, key_optional…)`——零新代码即可用。
2. `api_key_env.py`：`PROVIDER_API_KEY_ENV[provider] = "XXX_API_KEY"`。
3. `model_catalog.py`：`MODEL_OPTIONS[provider] = {"quick": [(label, id)…], "deep": […]}`；私有模型走 `_CUSTOM_ONLY`。
4. 特殊行为：`capabilities.py` 声明能力（如 DeepSeek 的 reasoning 往返）；需要专属 Chat 子类时参考 `DeepSeekChatOpenAI`。
5. `validators.py`：任意模型白名单按需加入。
6. GUI 无需改——「查询可用模型」会自动探测代理 `/v1/models`。

### 7.6 新增 A股特色功能

1. 数据函数放 `dataflows/a_stock/`（或 akshare_vendor）。
2. `tradingagents_api/astock_features.py`：`FEATURE_TABLE` 加条目（feature key → 调用 + 参数 + 解析器）；结构化解析器优先，透传 `_passthrough_parser` 兜底。
3. 前端 `lib/types.ts` 加 `AstockFeatureKey` + 数据接口；`astock/` 新面板组件；`AstockFeatureTabs` 注册 tab。
4. 测试：dispatch + 解析器单测。

### 7.7 新增 API 端点

1. `routers/` 新文件或既有文件加 `@router.get/post`（现有 router 均用完整字面路径，无前缀参数）。
2. `schemas.py` 定义请求/响应模型（**记得导入 `Any`**——见 §9）。
3. `server.py` 注册 router。
4. 前端 `lib/api.ts` 加方法 + `types.ts` 加接口。

### 7.8 新增 GUI 阶段/面板

1. `src/stores/useAnalysisStore.ts` 的 `Phase` 联合类型加值。
2. 组件放 `src/components/<domain>/`，App.tsx 中 `lazy()` + Suspense + ErrorBoundary 包裹。
3. 需要全局状态时新建 zustand store（勿往 App.tsx 加 useState——那里被刻意清空过）。

---

## 8. 测试指南

### 8.1 套件概览（1025 passed, 1 skipped 基线）

| 测试文件 | 用例数 | 覆盖 |
|----------|--------|------|
| test_chart_engine.py | 83 | 引擎①：周期/指标/画线/门面/复盘 |
| test_chart_data.py | 42 | 图表数据端点管线 |
| test_portfolio_engine.py | 28 | 引擎⑤ |
| test_signal_engine.py | 22 | 引擎③ |
| test_screener_engine.py | 21 | 引擎④ |
| test_data_center.py | 19 | 引擎② |
| test_backtesting.py | 19 | 回测（akquant 缺失自动 skip） |
| test_data_cache.py / test_portfolio.py / test_signal_processing.py / test_ohlcv_cache_freshness.py | 73 | 数据缓存/历史组合/信号处理/缓存新鲜度 |
| test_akshare_vendor.py | 12 | vendor 注册与路由 |
| test_progress_callback.py / test_temperature_config.py / test_deepseek_reasoning.py 等 | ~700 | 回调/温度转发/多平台 LLM/Agent 图/API 端点 |

引擎相关合计 288 个用例。前端 `npm test` 跑 vitest（chart-utils 等纯函数单测）。

### 8.2 约定与技巧

- **skip 条件**写在模块级 `pytestmark`：可选依赖缺失（akquant/langchain_aws）、线上凭证缺失（`DEEPSEEK_API_KEY`——直连官方 API 的冒烟测试，与 GUI 平台配置无关）。
- **Windows 两大坑**：
  1. SQLite 文件锁——fixture 必须 `yield` 后 `mgr.close()`，否则下个用例 PermissionError；
  2. pandas `Timestamp` 不能直接 `json.dumps`——序列化前 `v.isoformat()` / `pd.isna(v)→None`。
- **合成数据技巧**：测超买信号时，单调递增序列每根 +5 点（+3 不够，EMA 平滑会稀释 RSI 到 70 以下）。
- 线上 LLM 冒烟测试用环境变量控制，CI 无凭证自动跳过。

---

## 9. 已知坑与调试经验

| # | 坑 | 症状 | 根因/解法 |
|---|----|------|-----------|
| 1 | `get_config` 导入路径错 | 数据缓存静默失效 | 必须从 `tradingagents.dataflows.config` 导入，**不是** `tradingagents.default_config`（曾在 3 处犯过，已修复） |
| 2 | `ConfigSaveRequest` 未导入 `Any` | 反序列化重建时 NameError | schemas.py 隐患；PEP 563 惰性求值暂未爆雷，待修 |
| 3 | 前端端口硬编码 | 换后端端口断连 | `api.ts:17` `BASE_URL="http://127.0.0.1:8420"`；Tauri 也不拉起后端 |
| 4 | `DrawingManager.ts` 死代码 | 误以为是画线实现 | 真实实现是 `DrawingOverlay.tsx` 透明 canvas；lightweight-charts 方案已弃 |
| 5 | 选股/组合两套实现 | 改引擎不生效 | HTTP 层（screener.py/portfolio.py）未接引擎模块——见 §4.7 |
| 6 | RSI 全 NaN / 信号不触发 | 计算除零、EMA 稀释 | 除零替换 1e-10；测试数据斜率要够陡 |
| 7 | 看似"新数据源" | 误解为重复造轮子 | `data_center` 是对既有 `dataflows` 的门面封装+缓存，不替换 |
| 8 | 429 重试与去重冲突 | 恢复后事件重复/丢失 | graph_runner 重试时 `trace.clear()` + `completed_keys.clear()`，TaskState 按 `agent:status` 去重兜底 |
| 9 | akquant 安装偶发失败 | pip 找不到版本 | PyPI 有（0.3.52），重试即可；Rust 内核预编译 wheel，无需 cargo |
| 10 | 调试卡住的分析 | 难定位卡在哪个智能体 | 根目录 `debug_stall.py`；`ProgressCallbackHandler` 事件流 + 15s 心跳即为此设计 |

---

## 10. 发布与打包

### 10.1 可选依赖矩阵（pyproject.toml）

| extra | 内容 | 何时装 |
|-------|------|--------|
| dev | ruff / pytest / pytest-subtests | 开发必装 |
| gui | fastapi / granian / uvicorn | API 服务 |
| astock | akshare | A股数据 |
| backtest | akquant | 回测 |
| bedrock | langchain-aws | AWS Bedrock |

### 10.2 一键启动流程（start_gui.py）

1. 设 `BACKEND_PORT=8420`、`BACKEND_HOST=127.0.0.1`；
2. 拉起 granian（ASGI）；
3. 探测健康检查通过后，查找并启动 Tauri 产物 `tradingagents_gui/target/release/tradingagents-gui.exe`（兼容旧 `src-tauri/target/` 路径）。

### 10.3 Tauri 发布要点

- Release profile：`lto=true, codegen-units=1, opt-level="s", strip=true`（体积优化）。
- capabilities 最小化：dialog(save/ask)、fs(write-text-file/exists/mkdir)、notification——报告导出与桌面通知所需。
- **后端不打包进安装包**——Python 环境需单独分发（当前设计如此，见 §9 #3 的改进空间：可考虑 sidecar 化）。

---

*配套：功能清单 [FEATURES.md](FEATURES.md) ｜ 设计原则 [specs/2026-08-29-tdx-style-platform-design.md](specs/2026-08-29-tdx-style-platform-design.md)*
