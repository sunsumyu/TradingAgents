# TradingAgents 实现文档

> 版本: v0.4.0 | 更新: 2026-08-28

---

## 一、项目定位与竞品分析

### 1.1 定位

TradingAgents 是**全球首个基于多智能体 LLM 协作的金融分析框架**，将真实交易公司的组织架构映射为 AI 代理团队。与传统量化平台不同，TradingAgents 的核心价值在于：

- **认知层决策**：不是回测策略执行，而是多维度分析后的投资判断
- **自然语言交互**：用户用中文/英文描述需求，系统返回可读的分析报告
- **多智能体协作**：分析师、研究员辩论、风险管理、投资组合经理的完整决策链

### 1.2 开源竞品对比

| 维度 | TradingAgents | vnpy | QuantConnect (Lean) | backtrader | FreqTrade | Jesse |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| **核心能力** | LLM 多智能体分析 | 量化交易框架 | 算法回测+实盘 | 回测框架 | 加密货币交易 | 加密货币策略 |
| **AI/LLM 集成** | ✅ 核心特性 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **多智能体协作** | ✅ 6 层架构 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **A 股支持** | ✅ 原生 | ✅ 原生 | ⚠️ 需适配 | ❌ | ❌ | ❌ |
| **美股支持** | ✅ yfinance | ⚠️ 需适配 | ✅ 原生 | ⚠️ 需数据源 | ❌ | ⚠️ |
| **加密货币** | ⚠️ 基础 | ⚠️ 需适配 | ✅ | ❌ | ✅ 原生 | ✅ 原生 |
| **实时行情** | ✅ WebSocket | ✅ CTP/XTP | ✅ | ❌ | ✅ | ✅ |
| **回测引擎** | ⚠️ 基础 | ✅ | ✅ 专业级 | ✅ | ✅ | ✅ |
| **GUI** | ✅ Tauri 桌面 | ✅ Qt | ✅ Web | ❌ | ✅ FreqUI | ✅ Web |
| **策略语言** | 自然语言 | Python | C#/Python | Python | Python | Python |
| **学习曲线** | 低 | 中 | 高 | 中 | 中 | 中 |
| **社区活跃度** | 🔥 高 | 🔥 高 | 🔥 高 | 🟡 中 | 🔥 高 | 🟡 中 |
| **Stars** | 12k+ | 25k+ | 10k+ | 14k+ | 30k+ | 6k+ |

### 1.3 竞品详细分析

#### vnpy (25k+ Stars)
中国最大的开源量化交易框架，覆盖从数据到实盘的全链路。

**优势**：
- CTP/XTP/恒生等国内交易所接口原生支持
- 完整的策略回测和实盘交易引擎
- GUI (vnstation) 成熟稳定
- 社区庞大，插件丰富

**不足**：
- 无 AI/LLM 能力
- 策略开发门槛较高（需理解事件驱动模型）
- 分析维度依赖人工编码的技术指标

**TradingAgents 差异化**：vnpy 是"执行层"框架，TradingAgents 是"认知层"框架。两者可互补——TradingAgents 生成交易决策，vnpy 执行交易。

#### QuantConnect Lean (10k+ Stars)
全球最大的算法交易平台，支持股票、期货、外汇、加密货币。

**优势**：
- 多资产类别支持
- 机构级回测引擎（滑点、手续费、融资融券模拟）
- Jupyter Notebook 集成
- 云端 + 本地部署

**不足**：
- A 股支持需要自行适配数据源
- 无自然语言交互
- 学习曲线陡峭（需掌握 Framework 和 Algorithm 类）

**TradingAgents 差异化**：Lean 是"策略执行引擎"，TradingAgents 是"投资决策引擎"。Lean 可作为 TradingAgents 的下游执行层。

#### backtrader (14k+ Stars)
Python 生态最流行的回测框架，以简洁的 API 和丰富的技术指标著称。

**优势**：
- API 设计简洁优雅
- 内置 100+ 技术指标
- 支持多数据源、多时间框架
- 社区教程丰富

**不足**：
- 无实时交易能力
- 无 AI 集成
- 已进入维护模式（核心开发者减少）

**TradingAgents 差异化**：backtrader 是"回测工具"，TradingAgents 是"分析决策系统"。

#### FreqTrade (30k+ Stars)
专注加密货币的开源交易机器人，支持多交易所。

**优势**：
- 交易所集成丰富（Binance, OKX, Bybit 等）
- Telegram Bot 控制
- Hyperopt 自动调参
- FreqUI Web 界面

**不足**：
- 仅支持加密货币
- 无 AI 分析能力
- 策略基于技术指标，缺乏基本面分析

**TradingAgents 差异化**：FreqTrade 是"自动化执行机器人"，TradingAgents 是"智能分析顾问"。

### 1.4 与量化平台的功能对标

对标聚宽 (JoinQuant)、米筐 (RiceQuant)、优矿 (Uqer) 等中国主流量化平台：

| 功能模块 | 聚宽 | 米筐 | TradingAgents | 差异说明 |
|---------|:---:|:---:|:---:|---------|
| **因子库** | ✅ 300+ | ✅ 200+ | ⚠️ 按需获取 | 量化平台预计算；TradingAgents 按分析需求实时获取 |
| **财务数据** | ✅ 完整 | ✅ 完整 | ✅ 东方财富/新浪 | 数据源不同，覆盖度相当 |
| **新闻舆情** | ⚠️ 基础 | ⚠️ 基础 | ✅ LLM 深度分析 | TradingAgents 用 LLM 解读新闻含义 |
| **研报分析** | ❌ | ❌ | ✅ 多智能体辩论 | 核心差异化能力 |
| **技术分析** | ✅ 指标 | ✅ 指标 | ✅ 指标 + LLM 解读 | TradingAgents 不仅计算指标，还解读含义 |
| **策略回测** | ✅ 专业级 | ✅ 专业级 | ⚠️ 基础 | 量化平台核心优势 |
| **模拟交易** | ✅ | ✅ | ✅ 模拟组合 | TradingAgents 有虚拟组合管理 |
| **实盘对接** | ✅ 券商API | ✅ 券商API | ❌ | TradingAgents 聚焦分析，不对接券商 |
| **AI 分析** | ❌ | ❌ | ✅ 核心特性 | TradingAgents 独有优势 |
| **自然语言交互** | ❌ | ❌ | ✅ | 用户用自然语言描述需求 |

---

## 二、完整功能设计

### 2.1 功能架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TradingAgents 功能全景图                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        🧠 智能分析引擎 (Core)                        │    │
│  │                                                                     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │    │
│  │  │ 市场分析 │ │ 情绪分析 │ │ 新闻分析 │ │ 基本面   │              │    │
│  │  │ Analyst  │ │ Analyst  │ │ Analyst  │ │ Analyst  │              │    │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘              │    │
│  │       └────────────┼───────────┼────────────┘                      │    │
│  │                    ▼           ▼                                     │    │
│  │            ┌──────────────────────────┐                             │    │
│  │            │  多空研究员辩论 (Bull/Bear) │                             │    │
│  │            └────────────┬─────────────┘                             │    │
│  │                         ▼                                            │    │
│  │            ┌──────────────────────────┐                             │    │
│  │            │  研究经理 → 投资计划       │                             │    │
│  │            └────────────┬─────────────┘                             │    │
│  │                         ▼                                            │    │
│  │            ┌──────────────────────────┐                             │    │
│  │            │  交易员 → 交易提案         │                             │    │
│  │            └────────────┬─────────────┘                             │    │
│  │                         ▼                                            │    │
│  │            ┌──────────────────────────┐                             │    │
│  │            │  风险管理辩论 (3 角色)     │                             │    │
│  │            └────────────┬─────────────┘                             │    │
│  │                         ▼                                            │    │
│  │            ┌──────────────────────────┐                             │    │
│  │            │  投资组合经理 → 最终决策   │                             │    │
│  │            └──────────────────────────┘                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        📊 数据层 (Data Layer)                        │    │
│  │                                                                     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │    │
│  │  │ Yahoo    │ │ Alpha    │ │ A 股     │ │ FRED /   │              │    │
│  │  │ Finance  │ │ Vantage  │ │ 多源     │ │ Polymarket│              │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │    │
│  │                                                                     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │    │
│  │  │ Reddit   │ │ StockTwits│ │ 新闻    │ │ 研报     │              │    │
│  │  │ (社交)   │ │ (社交)   │ │ (媒体)   │ │ (券商)   │              │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        🖥️ 展示层 (Presentation)                      │    │
│  │                                                                     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │    │
│  │  │ Tauri    │ │ Web GUI  │ │ CLI      │ │ API      │              │    │
│  │  │ 桌面应用 │ │ (React)  │ │ (Rich)   │ │ (REST)   │              │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        🔧 工具层 (Tooling)                           │    │
│  │                                                                     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │    │
│  │  │ 选股器   │ │ 虚拟组合 │ │ 实时行情 │ │ 回测     │              │    │
│  │  │ Screener │ │ Portfolio│ │ Realtime │ │ Backtest │              │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块详细设计

#### 模块 1: 智能分析引擎

**功能描述**: 模拟真实交易公司的组织架构，通过 6 层智能体协作完成投资决策。

| 角色 | 输入 | 处理 | 输出 | LLM 模型 |
|------|------|------|------|---------|
| 市场分析师 | K 线数据、技术指标 | MACD/RSI/KDJ/Bollinger 解读 | 市场技术分析报告 | quick_thinking |
| 情绪分析师 | StockTwits/Reddit 帖子 | 情绪评分、关键词提取 | 社交情绪报告 | quick_thinking |
| 新闻分析师 | 新闻标题、宏观数据 | 事件影响评估 | 新闻事件报告 | quick_thinking |
| 基本面分析师 | 财务三表、估值指标 | PE/PB/ROE 分析 | 基本面分析报告 | quick_thinking |
| 多空研究员 | 分析师报告 | 多轮辩论 | 投资论点 | deep_thinking |
| 研究经理 | 辩论记录 | 综合评判 | 投资计划 (结构化) | deep_thinking |
| 交易员 | 投资计划 | 风险收益评估 | 交易提案 (结构化) | deep_thinking |
| 风险管理 | 交易提案 | 多角度风险评估 | 风险报告 | deep_thinking |
| 投资组合经理 | 风险报告 + 历史记忆 | 最终决策 | 5 级评级 | deep_thinking |

**5 级评级体系**:
- `Strong Buy` (强烈买入) — 高置信度买入信号
- `Buy/Overweight` (买入/超配) — 正面但非极端
- `Hold/Neutral` (持有/中性) — 无明确方向
- `Sell/Underweight` (卖出/低配) — 负面信号
- `Strong Sell` (强烈卖出) — 高置信度卖出信号

**辩论机制**:
- 研究辩论: 最多 N 轮 (可配置 1-5)，看多/看空研究员交替发言
- 风险辩论: 3 个角色 (激进派/保守派/中性派) 多轮讨论
- 每轮辩论后 Research Manager 给出阶段性评判

#### 模块 2: A 股数据中心

**功能描述**: 为 A 股投资者提供多维度数据工具，覆盖 7 大分析维度。

| 功能 | 数据源 | 更新频率 | 用途 |
|------|--------|---------|------|
| **实时行情** | 腾讯财经 | 3 秒 | 盘中价格监控 |
| **K 线数据** | mootdx (通达信) + 新浪 | 日线/分钟线 | 技术分析 |
| **资金流向** | 东方财富 | 日度 | 主力/散户资金分析 |
| **北向资金** | 东方财富 | 日度 | 外资动向 |
| **龙虎榜** | 东方财富 | 收盘后 | 游资/机构席位 |
| **概念板块** | 东方财富 | 日度 | 热点题材追踪 |
| **筹码分布** | K 线量价 | 计算 | 成本分析 |
| **机构评级** | 同花顺 | 不定期 | EPS 共识预期 |
| **限售解禁** | 东方财富 | 预告 | 解禁压力评估 |
| **行业对比** | 东方财富 | 季度 | 同业 PE/PB 排名 |

**A 股分析师团队** (扩展自基础 4 人):

| 分析师 | 专注领域 | 数据工具 |
|--------|---------|---------|
| 政策分析师 (Policy) | 宏观政策、行业监管 | 全球新闻 |
| 游资分析师 (Hot Money) | 游资动向、短线热点 | 资金流向 + 龙虎榜 + 概念板块 |
| 限售解禁分析师 (Lockup) | 解禁压力、筹码分布 | 限售数据 + 筹码分布 |

#### 模块 3: 多源数据路由

**功能描述**: 统一的数据访问接口，自动路由到最佳数据源。

```
用户请求 → interface.py → 供应商路由
                            ├── A 股? → a_stock/ (mootdx/东方财富/新浪/腾讯)
                            ├── 美股? → yfinance / Alpha Vantage
                            └── 宏观? → FRED / Polymarket
```

**数据源矩阵**:

| 数据类型 | 主源 | 备源 | 降级策略 |
|---------|------|------|---------|
| OHLCV 日线 | yfinance | Alpha Vantage | mootdx (A 股) |
| 分钟 K 线 | mootdx (A 股) | yfinance | 无 |
| 技术指标 | stockstats (本地计算) | Alpha Vantage | 无 |
| 基本面 | yfinance.info | Alpha Vantage | 东方财富 (A 股) |
| 财务三表 | Alpha Vantage | yfinance | 新浪财经 (A 股) |
| 新闻 | yfinance News | Alpha Vantage | 新浪财经 (A 股) |
| 社交情绪 | StockTwits + Reddit | — | 降级为空报告 |
| 宏观数据 | FRED | — | 降级为空 |
| 预测市场 | Polymarket | — | 降级为空 |

#### 模块 4: 桌面 GUI

**功能描述**: 基于 Tauri 2 + React 18 的跨平台桌面应用。

**界面模块**:

| 页面 | 功能 | 技术栈 |
|------|------|--------|
| **配置面板** | 参数输入、分析师选择、LLM 配置 | React + Zustand + Tailwind |
| **行情面板** | K 线图、技术指标、资金流向 | ECharts + WebSocket |
| **进度面板** | 5 阶段进度、实时日志流 | SSE + Zustand |
| **报告面板** | Markdown 报告、信号仪表盘 | react-markdown + ECharts |
| **选股器** | 自然语言查询、结果排序 | LLM + 表格 |
| **虚拟组合** | 持仓管理、P&L 曲线、交易记录 | Zustand + ECharts |
| **数据中心** | A 股 7 大维度数据卡片 | API + ECharts |

**设计语言**: AceternityUI 风格
- 发光卡片 (Glow Cards): 鼠标悬停时径向渐变高亮
- 玻璃态顶栏 (Glassmorphism): backdrop-blur + 半透明背景
- 渐变文字 (Gradient Text): 动画渐变色标题
- 微光骨架 (Shimmer Skeleton): 加载状态占位
- 光泽扫过按钮 (Shine Sweep): hover 时光泽动画

#### 模块 5: 选股器

**功能描述**: 自然语言驱动的股票筛选工具。

**工作流**:
```
用户输入: "找出 PE < 20 且 ROE > 15% 的白酒股"
    ↓
LLM 解析 → 结构化查询:
  { industry: "白酒", pe_ratio: { max: 20 }, roe: { min: 15 } }
    ↓
数据源执行 → 东方财富/同花顺查询
    ↓
结果排序 + LLM 评分 → 返回 Top N
```

**筛选维度**:
- 估值: PE、PB、PS、EV/EBITDA
- 盈利: ROE、ROA、净利润率、毛利率
- 成长: 营收增速、利润增速
- 规模: 总市值、流通市值
- 行业: 申万一级/二级行业
- 资金: 主力净流入、北向持仓
- 技术: 均线多头排列、MACD 金叉

#### 模块 6: 虚拟组合

**功能描述**: 模拟交易和组合管理，用于验证分析决策。

**功能清单**:
- **买入/卖出**: 按分析建议执行模拟交易
- **持仓管理**: 实时计算持仓盈亏
- **NAV 曲线**: 净值走势可视化
- **交易记录**: 每笔交易的时间、价格、原因
- **绩效指标**: 年化收益率、最大回撤、夏普比率

#### 模块 7: 实时行情

**功能描述**: WebSocket 推送 + HTTP 轮询的实时行情系统。

**数据源路由**:
- A 股 (6 位数字): 腾讯财经批量行情 (GBK 解析)
- 全球股票: yfinance fast_info (并发获取)

**推送协议**:
```json
// 客户端 → 服务端: 订阅
{ "tickers": ["600519", "AAPL", "0700.HK"] }

// 服务端 → 客户端: 推送 (每 3 秒)
{
  "600519": { "price": 1688.00, "change": -12.50, "changePct": -0.74, "name": "贵州茅台" },
  "AAPL":   { "price": 234.56, "change": 2.34, "changePct": 1.01, "name": "Apple Inc." }
}
```

#### 模块 8: 报告与可视化

**功能描述**: 分析结果的多维度可视化展示。

**图表类型**:

| 图表 | 数据 | 用途 |
|------|------|------|
| K 线图 (Candlestick) | OHLCV + MA/EMA/KDJ | 技术分析 |
| MACD 柱状图 | DIF/DEA/MACD | 趋势判断 |
| RSI 折线图 | RSI(6/12/24) | 超买超卖 |
| Bollinger 带 | 上轨/中轨/下轨 + 收盘价 | 波动率 |
| 资金流向图 | 主力/散户/北向 | 资金动向 |
| 信号仪表盘 | 信号 + 置信度 + 维度评分 | 决策概览 |
| NAV 曲线 | 每日净值 | 组合表现 |
| KDJ 交叉图 | K/D/J 三线 | 买卖点判断 |

#### 模块 9: 记忆与反思

**功能描述**: 跨运行的决策记忆和自我改进。

**机制**:
```
运行 1: 分析 NVDA → 决策 Buy → 执行
    ↓ (T+1 天)
运行 2: 获取 NVDA 实际收益 → 生成反思 → 注入 Portfolio Manager 提示词
    ↓
运行 3: 同一标的 → 带历史决策 + 反思 → 更明智的决策
```

**存储**:
- 决策日志: `~/.tradingagents/memory/trading_memory.md` (Markdown 追加)
- 反思生成: 自动获取实际收益 vs Alpha (相对 SPY)
- 注入方式: 最近 3 条同标的决策 + 最近 5 条跨标的反思

#### 模块 10: 检查点与恢复

**功能描述**: LangGraph 状态持久化，支持崩溃恢复和断点续跑。

**机制**:
- 每个节点执行后自动保存状态到 SQLite
- 崩溃后从最后成功步骤恢复，而非重新开始
- 每 ticker 独立数据库: `~/.tradingagents/cache/checkpoints/<TICKER>.db`

---

## 三、技术架构

### 3.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              客户端层                                       │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐               │
│  │  Tauri 桌面    │  │  浏览器 (SPA)  │  │  CLI (Rich)    │               │
│  │  React + Rust  │  │  React + Vite  │  │  Typer + Rich  │               │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘               │
└──────────┼───────────────────┼───────────────────┼─────────────────────────┘
           │ HTTP/SSE/WS       │ HTTP/SSE/WS       │ Python API
           ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API 网关层 (FastAPI)                               │
│                                                                             │
│  routers/health.py    ─  健康检查                                           │
│  routers/providers.py ─  LLM 提供商/模型                                    │
│  routers/analysis.py  ─  分析生命周期                                       │
│  routers/market.py    ─  行情数据                                           │
│  routers/astock.py    ─  A 股数据工具                                       │
│  routers/screener.py  ─  选股器                                             │
│  routers/portfolio.py ─  虚拟组合                                           │
│  routers/realtime.py  ─  实时行情 (HTTP + WebSocket)                        │
│  routers/config.py    ─  YAML 配置                                          │
│  routers/cache.py     ─  缓存管理                                           │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────────────┐
│                          核心引擎层 (tradingagents/)                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  graph/ — LangGraph 编排                                           │    │
│  │    trading_graph.py  ─  主编排类 (Facade)                           │    │
│  │    tool_wiring.py    ─  分析师→工具注册表 (Registry)                 │    │
│  │    setup.py          ─  图结构构建                                   │    │
│  │    propagation.py    ─  状态初始化                                   │    │
│  │    conditional_logic.py ─ 条件路由                                  │    │
│  │    checkpointer.py   ─  检查点管理                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  agents/ — 智能体实现                                              │    │
│  │    analysts/    ─  4 个基础分析师 + 3 个 A 股分析师                  │    │
│  │    researchers/ ─  看多/看空研究员                                  │    │
│  │    managers/    ─  研究经理 + 投资组合经理                           │    │
│  │    trader/      ─  交易员                                           │    │
│  │    risk_mgmt/   ─  3 个风险管理角色                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  llm_clients/ — LLM 抽象层                                         │    │
│  │    factory.py        ─  工厂: create_quick_llm / create_deep_llm    │    │
│  │    openai_client.py  ─  OpenAI/DeepSeek/Qwen/Groq/Mistral          │    │
│  │    anthropic_client.py ─ Anthropic Claude                           │    │
│  │    google_client.py  ─  Google Gemini                               │    │
│  │    model_catalog.py  ─  模型目录 (18+ 提供商)                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────────────┐
│                          数据层 (dataflows/)                                 │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  interface.py ─  供应商路由 (DIP + Strategy)                        │    │
│  │    A 股? → a_stock/                                                 │    │
│  │    美股? → yfinance / Alpha Vantage                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  a_stock/ ─  A 股数据 vendor (Facade 模式, 10 个子模块)              │    │
│  │    mootdx_client.py  ─  通达信 TCP 客户端 (单例)                    │    │
│  │    tencent_quote.py  ─  腾讯财经批量行情                            │    │
│  │    eastmoney.py      ─  东方财富 datacenter                         │    │
│  │    sina_finance.py   ─  新浪财经 K 线 + 财务                        │    │
│  │    tonghuashun.py    ─  同花顺 EPS 共识                              │    │
│  │    chip_distribution.py ─ 筹码分布计算                              │    │
│  │    northbound_flow.py ─  北向资金 CSV 缓存                           │    │
│  │    ohlcv.py          ─  OHLCV 加载 (A 股 + Sina 补充)               │    │
│  │    utils.py          ─  ticker 归一化、日期验证                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  y_finance.py       ─  Yahoo Finance vendor                        │    │
│  │  yfinance_news.py   ─  Yahoo 新闻 + 搜索                           │    │
│  │  alpha_vantage/     ─  Alpha Vantage vendor (5 个子模块)            │    │
│  │  stockstats_utils.py ─  技术指标计算 (本地)                         │    │
│  │  fred.py            ─  美联储宏观经济数据                            │    │
│  │  polymarket.py      ─  Polymarket 预测市场                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────────────┐
│                          持久化层                                            │
│                                                                             │
│  data_cache.py ─  SQLite WAL 缓存 (cached_fetch 上下文管理器)               │
│  checkpointer  ─  LangGraph SQLite 检查点                                  │
│  memory_log    ─  Markdown 决策日志                                         │
│  reporting/    ─  Markdown 报告生成                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **前端框架** | React | 18.3 |
| **构建工具** | Vite | 5.4 |
| **CSS 框架** | Tailwind CSS | 3.4 |
| **状态管理** | Zustand | 5.0 |
| **图表库** | ECharts | 5.5 |
| **桌面壳** | Tauri | 2.x |
| **后端框架** | FastAPI | 0.115 |
| **ASGI 服务器** | granian | 2.8 |
| **图编排** | LangGraph | 0.2 |
| **LLM 框架** | LangChain | 0.3 |
| **数据验证** | Pydantic | v2 |
| **数据库** | SQLite (WAL) | 3.x |
| **Python** | Python | 3.10+ |

### 3.3 设计模式总览

| 模式 | 应用位置 | 效果 |
|------|---------|------|
| **Facade** | `server.py`, `a_stock/__init__.py` | 简化复杂子系统为统一接口 |
| **Registry** | `tool_wiring.py` (ANALYST_TOOLS) | 分析师→工具映射为声明式字典 |
| **Factory** | `llm_clients/factory.py` | LLM 客户端创建与提供商解耦 |
| **Strategy** | `llm_clients/` 家族 | 18+ 提供商统一接口 |
| **Context Manager** | `cached_fetch` / `cached_fetch_raw` | 缓存生命周期自动管理 |
| **Adapter** | `NormalizedChatOpenAI` | 统一不同提供商的响应格式 |
| **Template Method** | 分析师节点 | 所有分析师遵循: prompt → llm.bind_tools → tool_call → report |
| **Observer** | `callbacks` 参数 | 统计信息、进度事件回调 |
| **Command** | `ToolNode` | 封装工具调用为图节点 |
| **SRP** | 10 个 APIRouter | 每个路由模块一个业务领域 |
| **Module** | `routers/`, `a_stock/` | 按功能域组织代码 |

### 3.4 数据库设计

#### SQLite WAL 缓存 (`data_cache.py`)

```sql
-- 每个 ticker 独立数据库
CREATE TABLE IF NOT EXISTS cache (
    key     TEXT PRIMARY KEY,
    value   BLOB,           -- JSON 序列化的数据
    type    TEXT,           -- 数据类型标记
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

PRAGMA journal_mode=WAL;    -- 支持并发读写
```

**缓存键格式**: `{feature}_{ticker}_{date}_{params_hash}`

**缓存层级**:
| 层级 | TTL | 说明 |
|------|-----|------|
| 日线 OHLCV | 当日有效 | 滑动窗口 5 年 |
| 技术指标 | 当日有效 | 依赖 OHLCV |
| 基本面 | 7 天 | 财务数据变化慢 |
| 新闻 | 24 小时 | 新闻时效性强 |
| A 股特征 | 24 小时 | 资金流向等日频数据 |

#### LangGraph 检查点 (`checkpointer.py`)

```sql
-- 每个 ticker 独立数据库
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT,
    checkpoint JSON,
    metadata   JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 四、API 接口文档

### 4.1 基础端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 健康检查 |
| `GET` | `/api/today` | 服务器日期 |
| `GET` | `/api/config` | 加载 YAML 配置 |
| `POST` | `/api/config` | 保存 YAML 配置 |

### 4.2 LLM 提供商

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/providers` | 所有提供商 + 模型列表 |
| `GET` | `/api/models/{provider}` | 特定提供商的模型 (支持代理查询) |

### 4.3 分析生命周期

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/analyze` | 启动分析任务, 返回 task_id |
| `GET` | `/api/analyze/{task_id}/stream` | SSE 实时进度流 |
| `GET` | `/api/report/{task_id}` | 获取完成的报告 |
| `GET` | `/api/report/{task_id}/sections/{section}` | 获取报告单个章节 |

**SSE 事件类型**:
- `progress`: 阶段/代理状态更新
- `token`: 流式文本 token
- `complete`: 分析完成 (含 ticker + signal)
- `error`: 分析失败

### 4.4 行情数据

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/market-data` | 市场数据预览 (K 线 + 指标 + 基本面 + 新闻) |
| `POST` | `/api/chart-data` | 图表数据 (可配置天数/分钟级别) |
| `POST` | `/api/realtime-prices` | 批量实时报价 |
| `WS` | `/ws/realtime` | WebSocket 实时推送 |

### 4.5 A 股数据工具

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/astock-features` | 13 种 A 股特征数据 |

**支持的特征**: `balance_sheet`, `cashflow`, `income_statement`, `profit_forecast`, `hot_stocks`, `northbound_flow`, `concept_blocks`, `fund_flow`, `dragon_tiger_board`, `lockup_expiry`, `chip_distribution`, `industry_comparison`, `insider_transactions`

### 4.6 选股器

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/screener` | 自然语言选股查询 |

### 4.7 虚拟组合

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/portfolio` | 当前组合 (持仓 + P&L) |
| `POST` | `/api/portfolio/trade` | 执行模拟交易 |
| `GET` | `/api/portfolio/history` | 交易历史 |
| `GET` | `/api/portfolio/nav` | NAV 曲线数据 |
| `POST` | `/api/portfolio/reset` | 重置组合 |

### 4.8 缓存管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/cache/clear` | 清除缓存 (按 ticker/类型) |
| `GET` | `/api/cache/stats` | 缓存统计信息 |

### 4.9 检查点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/checkpoints` | 列出所有可恢复的检查点 |
| `GET` | `/api/checkpoints/{ticker}` | 查询特定标的的检查点 |

---

## 五、部署指南

### 5.1 开发环境

```bash
# 后端
cd TradingAgents
python -m venv venv
venv\Scripts\activate  # Windows
pip install -e ".[dev]"
granian tradingagents_api.server:app --interface asgi --host 127.0.0.1 --port 8420

# 前端
cd tradingagents_gui
npm install
npm run dev  # http://localhost:5173
```

### 5.2 生产部署

```bash
# Docker
cp .env.example .env
docker compose up -d

# 或手动
granian tradingagents_api.server:app \
  --interface asgi \
  --host 0.0.0.0 \
  --port 8420 \
  --workers 4
```

### 5.3 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `llm_provider` | `openai` | LLM 提供商 |
| `quick_think_llm` | `gpt-4o-mini` | 快速思考模型 |
| `deep_think_llm` | `gpt-4o` | 深度思考模型 |
| `max_debate_rounds` | `1` | 多空辩论轮数 |
| `max_risk_discuss_rounds` | `1` | 风险辩论轮数 |
| `temperature` | `0` | 采样温度 |
| `data_cache_dir` | `~/.tradingagents` | 数据缓存目录 |
| `checkpoint_enabled` | `false` | 是否启用检查点 |
| `selected_analysts` | `["market","social","news","fundamentals"]` | 分析师团队 |

---

## 六、开发路线图

### 已完成 (v0.1.0 - v0.3.1)

- [x] 多智能体协作框架 (6 层架构)
- [x] 18+ LLM 提供商支持
- [x] 多数据源路由 (yfinance, Alpha Vantage, FRED, Polymarket)
- [x] A 股数据 vendor (mootdx, 东方财富, 新浪, 腾讯, 同花顺)
- [x] Tauri 桌面 GUI (React + ECharts)
- [x] 选股器 (自然语言 → 结构化查询)
- [x] 虚拟组合 (模拟交易 + NAV 曲线)
- [x] 实时行情 (WebSocket + HTTP)
- [x] 检查点恢复 (SQLite)
- [x] 记忆反思闭环 (跨运行决策学习)

### 进行中 (v0.4.0)

- [x] 架构重构: 缓存上下文管理器
- [x] 架构重构: 图工具注册表
- [x] 架构重构: A 股模块拆分
- [x] 架构重构: 服务器 APIRouter
- [ ] yfinance DIP 重构 (抽象 vendor 接口)

### 计划中 (v0.5.0+)

- [ ] 分析师并行化 (LangGraph Send API, 预计延迟降低 50-70%)
- [ ] 回测引擎增强 (滑点、手续费、融资融券模拟)
- [ ] 策略模板库 (预置常用分析策略)
- [ ] 多标的对比分析 (行业对比、概念对比)
- [ ] 移动端适配 (React Native / PWA)
- [ ] 实盘对接 (券商 API 网关)
- [ ] 团队协作 (多用户分析、权限管理)
- [ ] 国际化增强 (日韩语言支持)

---

## 七、贡献指南

### 代码规范

- Python: ruff (line-length=100, isort)
- TypeScript: ESLint + Prettier
- 提交信息: Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`)

### 测试要求

- 所有 PR 必须通过 `python -m pytest tests/ -x`
- 前端变更需通过 `npx vitest run`
- 新功能需添加测试用例

### 架构原则

- **SRP**: 每个模块/类只有一个职责
- **DIP**: 依赖抽象而非具体实现
- **OCP**: 通过注册表/工厂扩展，不修改核心代码
- **LSP**: 上下文管理器、接口契约
- **Facade**: 复杂子系统通过 facade 简化访问
