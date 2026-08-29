# TradingAgents 功能文档（对标通达信）

> **文档定位**：本手册从**使用者视角**完整描述平台功能，功能分类参考通达信（TDX）。
> 架构与接口实现细节见设计文档 [`2026-08-29-tdx-style-platform-design.md`](specs/2026-08-29-tdx-style-platform-design.md)。
>
> **状态标记**：✅ 完整可用 ｜ ⚠️ 部分实现 ｜ 📋 仅后端 API（无界面）｜ 📱 仅前端（无后端）

---

## 目录

1. [概述与功能地图](#1-概述与功能地图)
2. [行情看盘](#2-行情看盘)
3. [K线与技术分析](#3-k线与技术分析)
4. [智能选股](#4-智能选股)
5. [预警系统](#5-预警系统)
6. [模拟交易与组合管理](#6-模拟交易与组合管理)
7. [策略回测](#7-策略回测)
8. [A股特色数据](#8-a股特色数据)
9. [AI 多智能体分析](#9-ai-多智能体分析)
10. [数据源与缓存](#10-数据源与缓存)
11. [API 接口总览](#11-api-接口总览)
12. [通达信功能对照表](#12-通达信功能对照表)
13. [已知差距与后续路线](#13-已知差距与后续路线)

---

## 1. 概述与功能地图

TradingAgents 是一套**「AI 多智能体分析 + 通达信式看盘工具」**二合一的股票分析平台：

- **看盘侧**对标通达信：K线多周期、技术指标、画线工具、选股器、预警、模拟炒股、A股特色数据（筹码/龙虎榜/北向等）。
- **分析侧**是通达信没有的：多智能体（4 分析师 + 多轮辩论）AI 研究，产出结构化交易决策报告，并支持把 AI 决策直接送入回测。

### 功能目录树（对标通达信菜单）

```
TradingAgents
├── 行情看盘
│   ├── 实时行情（A股批量 / 全球）
│   ├── 自选股分组管理
│   ├── 周期切换（1分钟 ~ 年线，共13种）
│   └── 多图布局（1×1 / 1×2 / 2×2）
├── 技术分析
│   ├── K线图（前复权，MA 叠加，十字光标）
│   ├── 技术指标（25 种，参数可调）
│   ├── 画线工具（15 种，撤销/重做）
│   ├── K线复盘（逐根回放）
│   └── 自动信号检测（MACD/RSI/KDJ）
├── 智能选股
│   ├── 条件选股（50 个字段 × 10 种运算符）
│   ├── 预设模板（10 套）
│   └── 自然语言选股
├── 预警系统
│   ├── 价格预警（桌面通知）
│   └── 信号引擎预警
├── 交易工具
│   ├── 模拟炒股（组合管理）
│   ├── 绩效分析（Sharpe/回撤/胜率）
│   └── 策略回测（akquant）
├── A股特色数据
│   ├── 筹码分布 ｜ 龙虎榜 ｜ 北向资金
│   ├── 概念板块 ｜ 盈利预测 ｜ 解禁日历
│   └── 人气榜 ｜ 行业对比 ｜ 三大报表
├── AI 智能分析（核心差异功能）
│   ├── 多智能体研究（市场/情绪/新闻/基本面）
│   ├── 多 LLM 平台配置
│   └── 报告可视化 + 决策回测
└── 数据管理
    ├── 6 大数据源路由
    ├── SQLite 本地缓存
    └── 断点续析
```

---

## 2. 行情看盘

### 2.1 实时行情 ✅

- **功能**：批量获取股票实时报价（价格、涨跌幅、成交量、买卖五档）。
- **数据源**：A股走腾讯批量行情接口；全球标的走 yfinance。
- **使用方式**：
  - GUI：主图表页自动刷新（`useRealtimePrices`），自选股面板同步显示。
  - API：`POST /api/realtime-prices`（批量）；`WS /ws/realtime`（推送）。
- **后端模块**：`tradingagents/data_center/center.py` → `DataCenter.get_realtime()`。

### 2.2 自选股分组 📱

- **功能**：右侧自选股侧栏，支持多分组管理，点击直接切换主图标的；分组存本地（localStorage），重启不丢。
- **使用方式**：GUI → 图表页右侧 `WatchlistPanel`，右键/按钮添加、移动、删除。
- **对标通达信**：自选股板块（06 视图）。
- **说明**：纯前端实现，未同步到后端。

### 2.3 周期切换 ✅

- **功能**：13 种K线周期，覆盖分钟线到长线：

| 分组 | 周期 |
|------|------|
| 分钟线 | 1m、2m、3m、5m、15m、30m、60m |
| 日线以上 | 日线、周线、月线、季线、年线 |
| 其他 | 全部历史（ALL） |

- **使用方式**：GUI → 图表上方 `TimeframeSelector` 一键切换；支持中文标签模糊匹配（如"日线"、"周线"）。
- **后端模块**：`chart_engine/timeframes.py` → `Timeframe` 枚举 + `TIMEFRAME_REGISTRY`。

### 2.4 多图布局 ✅

- **功能**：主图区支持 1×1（单图）、1×2（双图并排）、2×2（四图同屏）布局，每个窗格独立周期/指标/标的。
- **使用方式**：GUI → 图表页布局切换按钮（`MultiChartLayout`）。
- **对标通达信**：多窗口组合视图。

---

## 3. K线与技术分析

### 3.1 K线图 ✅

- **功能**：ECharts 蜡烛图，默认前复权（qfq），叠加 MA 均线、成交量副图；十字光标联动显示 OHLC 与指标数值；支持截图导出（PNG）。
- **使用方式**：GUI → 主图表区 `TradingViewChart`；头部 `ChartHeader` 显示代码/现价/涨跌幅。
- **对标通达信**：K线图（主图）。

### 3.2 技术指标（25 种）✅

所有指标集中在 `INDICATOR_LIBRARY`，分三类：

| 类别 | 指标 | 数量 |
|------|------|------|
| **主图叠加** | MA、EMA、BOLL（布林带）、SAR（抛物线）、ATR（真实波幅） | 5 |
| **副图摆动** | MACD、RSI、KDJ、WR（威廉）、CCI、DMI（+ADX）、TRIX、DMA、ROC、MTM、BIAS、ASI、EMV、ARBR、CR、DMIADX | 16 |
| **量能类** | VR（成交量比率）、OBV（能量潮）、VWAP（量价均线）、MV（均量） | 4 |

- **参数可调**：每个指标带默认参数与合法参数区间，GUI 中 `IndicatorParamDialog` 可视化调整（如 MA 的 5/10/20/60）。
- **副图插槽**：3 个副图槽位，可放 MACD / RSI / KDJ / WR / CCI / BOLL 任意组合，点击表头切换。
- **使用方式**：GUI → `IndicatorBar` 勾选指标；副图 `SubPanels` 切换。
- **API**：`POST /api/chart-data`（图表+指标数据）；`POST /api/indicators` 类计算走 chart_data 内部 `computors.py`。
- **后端模块**：`chart_engine/indicators.py` → `IndicatorComputer.compute()` / `compute_batch()`。

### 3.3 画线工具（15 种）✅

| 工具 | 用途 |
|------|------|
| 十字光标 crosshair | 定位参考 |
| 趋势线 trendline | 两点连线 |
| 水平线 horizontal_line | 支撑/压力位 |
| 垂直线 vertical_line | 时间标记 |
| 矩形 rectangle | 区域标注 |
| 斐波那契 fibonacci | 7 档回撤位（0 / 23.6 / 38.2 / 50 / 61.8 / 78.6 / 100%） |
| 平行通道 parallel_channel | 通道趋势 |
| 安德鲁音叉 pitchfork | 中值轨道 |
| 江恩扇形 gann_fan | 江恩角度线 |
| 圆弧 arc / 椭圆 ellipse | 曲线标注 |
| 文字 text / 箭头 arrow | 注释 |
| 速度阻力线 speed_line | 斜率参考 |
| 时间周期 time_zone | 竖排时间栅栏 |

- **样式系统**：颜色、线宽、线型（实线/点线/虚线/长虚线）、填充色、透明度、字号均可配。
- **编辑能力**：拖拽移动锚点、删除、清空、**撤销/重做**；图形随K线缩放联动（基于 time_index + price 坐标）。
- **使用方式**：GUI → `DrawingToolbar` 画线，`DrawingOverlay` 渲染，`DrawingManager` 管理历史。
- **对标通达信**：画线工具 F（TDX 的直线/甘氏线/斐波那契等）。

### 3.4 K线复盘 ✅

- **功能**：像播放器一样逐根回放历史K线（可调速），训练盘感；复盘状态下指标逐根重算。
- **使用方式**：GUI → 图表页 `ReplayControls` 时间滑块。
- **后端模块**：`chart_engine/renderer.py` → `ChartEngine.replay()`（生成 `ChartSnapshot` 流）。
- **对标通达信**：盘后复盘（训练模式）。

### 3.5 自动信号检测 ✅

- **功能**：指标计算时自动探测买卖信号，当前覆盖：
  - **MACD**：金叉（BUY）/ 死叉（SELL）
  - **RSI**：超买 >70（SELL）/ 超卖 <30（BUY）
  - **KDJ**：低位金叉（BUY）/ 高位死叉（SELL）
- **信号结构**：类型（BUY/SELL/HOLD）+ 强度（0-100，分 STRONG/MODERATE/WEAK/NEUTRAL 四档）+ 触发原因。
- **GUI**：`SignalDashboard` 汇总展示当前标的的信号面板。
- **后端模块**：`chart_engine/indicators.py` 信号探测器；`signal_engine/engine.py` 复合信号。

---

## 4. 智能选股

对标通达信「智能选股 / 条件选股」。

### 4.1 条件选股 ✅

- **50 个筛选字段**，分 5 大类：

| 分类 | 字段示例 | 数量 |
|------|----------|------|
| 技术面 | pe_ratio 之外的 ma5/10/20/60、rsi_14、macd、kdj_k/d、boll_width、atr_14 等 | 19 |
| 基本面 | roe、净利润率、营收增速、bps 等 | 11 |
| 资金面 | northbound_flow、主力净流入、量比、20日均量等 | 6 |
| A股特色 | hot_rank（人气榜）、dragon_tiger（龙虎榜）、concept_count、lockup_days（解禁）、盈利预测 EPS/PE | 6 |
| 市场特性 | beta、52周高低、ipo_date、list_years、industry、region | 8 |

- **10 种运算符**：`>`、`<`、`>=`、`<=`、`=`、`!=`、`in`、`not_in`、`contains`、`between`。
- **多条件 AND 组合**，支持排序字段与结果条数限制。
- **使用方式**：GUI → 主页「智能选股」按钮 → `ScreenerPanel`；每只结果带评分条（ScoreBar），可一键跳转分析（`onAnalyzeTicker`）。
- **API**：`POST /api/screener`。
- **后端模块**：`screener_engine/engine.py` → `ScreenerEngine.screen()`。

### 4.2 预设模板（10 套）✅

| 模板 ID | 名称 | 策略思路 |
|---------|------|----------|
| `value` | 价值股筛选 | 低估值 + 稳健盈利 |
| `growth` | 成长股筛选 | 高营收/利润增速 |
| `momentum` | 动量突破 | 价格动量 + 量能配合 |
| `oversold` | 超跌反弹 | RSI 超卖 + 短期深跌 |
| `large_cap` | 大盘蓝筹 | 大市值 + 高流动性 |
| `small_cap_growth` | 小盘成长 | 小市值 + 高增长 |
| `dividend` | 高股息策略 | 股息率门槛 |
| `low_pe` | 低估值 | 市盈率下限筛选 |
| `high_volatility` | 高波动 | ATR/振幅门槛 |
| `northbound` | 北向资金流入 | 北向增持标的 |

- **使用方式**：GUI 选股页模板列表一键运行；API `POST /api/screener`（带 template）。
- **后端接口**：`get_templates()` / `run_template(template_id)`。

### 4.3 自然语言选股 ⚠️

- **功能**：输入中文描述直接选股，例如：
  - "PE低于20且ROE大于15%的股票"
  - "市值大于500亿、股息率超过3%的消费股"
  - "北向资金流入 + 半导体行业"
- **当前实现**：**正则规则解析**（覆盖 PE/PB/ROE/市值/涨幅/股息率/增速/RSI 数值条件 + 消费/科技/金融/医药/新能源/半导体行业词 + 北向/外资），非 LLM 解析——复杂组合条件可能识别不到。
- **后端模块**：`ScreenerEngine.screen_natural()`。
- **路线**：接入 LLM 客户端做完整自然语言 → 结构化条件转换（见 §13）。

---

## 5. 预警系统

### 5.1 价格预警（GUI）📱

- **功能**：对任意自选标的设置价格上/下破触发线；触发时弹**桌面通知**（Tauri 通知通道）。
- **管理**：`AlertPanel` 添加 / 删除 / 启停开关；规则存本地 localStorage，随实时行情轮询检查。
- **对标通达信**：价格预警。
- **说明**：纯前端实现，无后端持久化，换设备不同步。

### 5.2 信号引擎预警 ⚠️

- **功能**：程序化预警规则引擎，支持 7 种条件定义：

| 条件 | 说明 | 状态 |
|------|------|------|
| `price_above` / `price_below` | 价格上破/下破 | ✅ 已实现 |
| `volume_above` | 放量超过阈值 | ✅ 已实现 |
| `indicator_above` / `indicator_below` | 指标值越界 | ⚠️ 已定义未求值 |
| `cross_above` / `cross_below` | 上穿/下穿 | ⚠️ 已定义未求值 |

- **使用方式**：Python API —— `SignalEngine.add_alert(ticker, condition, threshold, message)` → `check_alerts(ticker, price, volume)`；无 GUI、无 HTTP 端点。
- **后端模块**：`signal_engine/engine.py`。

---

## 6. 模拟交易与组合管理

### 6.1 模拟炒股 ✅

对标通达信「模拟炒股」。

- **功能**：虚拟资金账户，支持买入/卖出，自动计算佣金（默认万三，最低 5 元）、持仓成本（多次买入加权平均）、持仓市值、浮动盈亏、仓位权重。
- **交易校验**：资金不足、持仓不足直接拒绝并报错说明。
- **组合汇总**：总资产 / 现金 / 持仓市值 / 总盈亏（额、%）/ 当日盈亏 / 逐只持仓明细。
- **使用方式**：GUI → 主页「模拟交易」按钮 → `PortfolioPanel`（下单、查持仓、查历史、清空重置）。
- **API**：
  - `GET /api/portfolio` — 持仓汇总
  - `POST /api/portfolio/trade` — 下单
  - `GET /api/portfolio/history` — 成交记录
  - `GET /api/portfolio/nav` — 净值曲线
  - `POST /api/portfolio/reset` — 重置账户
- **后端模块**：`portfolio_engine/engine.py` → `PortfolioEngine`。

### 6.2 绩效分析 ✅

- **功能**：一键生成绩效报告，指标包括：
  - 收益类：总收益率、年化收益率、基准收益（默认沪深300）、**Alpha**
  - 风险类：**Sharpe 比率**（年化，√252）、**最大回撤**
  - 交易类：总交易次数、胜负笔数、**胜率**、平均盈利/亏损、最佳/最差单笔、**盈亏比（Profit Factor）**
- **交易配对**：买卖按标的先进先出配对计算每笔收益率。
- **使用方式**：Python API `PortfolioEngine.get_performance(benchmark_return=...)`；组合页展示核心指标。
- **后端模块**：`portfolio_engine/engine.py`。

---

## 7. 策略回测 📋

- **功能**：基于 **akquant**（Rust 内核）的回测引擎，两种用法：
  1. **通用回测** `run()`：自定义 akquant 策略类 + 日期区间（akshare 前复权数据）。
  2. **AI 决策回测** `run_from_decision()`：把多智能体分析产出的交易决策（买入/卖出/观望，自动识别中英文关键词）转成策略，在决策日之后持有 N 天模拟，验证 AI 判断。
- **输出指标**：总收益、年化收益、Sharpe、最大回撤、胜率、盈亏笔数、平均单笔收益、期末资产；支持生成 Markdown 回测报告（存 `results/backtest/`）。
- **状态**：📋 仅后端 —— `POST /api/backtest` 已就绪，GUI 尚无入口。
- **后端模块**：`tradingagents/backtesting/`（engine / strategy / report）。
- **依赖**：`pip install "tradingagents[backtest]"`（akquant 为可选依赖，未安装时功能优雅降级）。

---

## 8. A股特色数据

对标通达信特色数据，统一入口：**仅当代码为 A 股时显示** `AstockFeatureTabs` 标签页；每个面板懒加载，无专属面板的功能回退为格式化文本渲染。

| 功能 | 说明 | 面板 | 状态 |
|------|------|------|------|
| 筹码分布 | 获利盘比例、成本分布、压力/支撑位 | `ChipPanel` | ✅ |
| 龙虎榜 | 上榜原因、席位明细、买卖金额 | `DragonTigerPanel` | ✅ |
| 北向资金 | 沪深港通净流入日度序列 | `NorthboundPanel` | ✅ |
| 概念板块 | 所属概念、行业、地区标签 | `ConceptPanel` | ✅ |
| 盈利预测 | 机构 EPS/PE 预测（多年对比） | `ProfitForecastPanel` | ✅ |
| 解禁日历 | 限售解禁时间表与规模 | `LockupPanel` | ✅ |
| 人气榜 | 个股热度排名 | `HotStockPanel` | ✅ |
| 行业对比 | 行业内估值/涨幅对比 | 文本渲染 | ⚠️ 无专属面板 |
| 股东动向 | 股东增减持 | 文本渲染 | ⚠️ 无专属面板 |
| 三大报表 | 资产负债表 / 现金流量表 / 利润表 | 文本渲染 | ⚠️ 无专属面板 |

- **API**：`POST /api/astock-features`（统一功能分发端点，13 个 feature key）。
- **后端模块**：`tradingagents_api/astock_features.py`；数据源为 `a_stock` / `akshare` vendor 的 signal_data 工具族。

---

## 9. AI 多智能体分析

本平台区别于通达信的核心功能。

### 9.1 多智能体研究流程 ✅

- **分析师团队**（可勾选）：
  - **Market Analyst** — 技术面（K线/指标/量价）
  - **Sentiment Analyst** — 市场情绪（社交媒体/热度）
  - **News Analyst** — 新闻与事件
  - **Fundamentals Analyst** — 基本面（财报/估值）
- **研究深度**：浅度（1 轮辩论）/ 中度（3 轮）/ 深度（5 轮）——多空研究员 + 研究经理辩论后产出最终交易决策（买入/卖出/观望 + 置信度）。
- **两步工作流**：先预览/确认市场数据（`MarketDataPanel`），再启动分析，避免脏数据白跑全程。
- **断点续析**：分析过程自动存 checkpoint，可中断后恢复（`GET /api/checkpoints/{ticker}`）。

### 9.2 多 LLM 平台配置 ✅

- **功能**：同时配置多个 LLM 平台（自定义名称 + 提供商协议 + API Key + 代理 URL），快速/深度模型可分别选自不同平台（如：深度用 Claude，快速用 GLM）。
- **连通性验证**：「查询可用模型」按钮实时探测代理的 `/v1/models`，成功后显示平台健康状态（绿点）。
- **API**：`GET /api/providers`（提供商目录）；`GET /api/models/{provider}?proxy_url=&api_key=`（代理模型探测）。

### 9.3 报告与可视化 ✅

- **报告渲染**：Markdown 分节标签页 + 关键词智能高亮（交易信号/指标/风险等级），支持搜索。
- **报告图表**：K线、MACD、RSI、布林带、资金流、信号仪表盘、基本面卡片、新闻流 8 类组件自动嵌入报告。
- **过程可视化**：`ProgressPanel` 实时展示各智能体进度流（SSE token 级推送）。
- **API**：`POST /api/analyze` → `GET /api/analyze/{task_id}/stream`（SSE）→ `GET /api/report/{task_id}`。

---

## 10. 数据源与缓存

### 10.1 数据源路由（6 大 vendor）✅

| Vendor | 定位 | 覆盖 |
|--------|------|------|
| `a_stock` | A股主数据源 | 行情/基本面/新闻/信号数据全套 |
| `akshare` | A股备选数据源（可选依赖） | 与 a_stock 同构的 17 个函数，配置切换 |
| `yfinance` | 全球市场 | 美股/港股/外汇/加密 |
| `alpha_vantage` | 全球补充 | 基本面/内幕交易/新闻 |
| `fred` | 宏观经济 | 利率/通胀/就业/GDP |
| `polymarket` | 预测市场 | 事件概率 |

- **配置方式**：`data_vendors` 按类别指定主源，逗号分隔多源自动故障转移（如 `"akshare,yfinance"`）；工具级 `tool_vendors` 可精确覆盖到单个方法。
- **无数据哨兵**：所有源都无数据时返回明确 `NO_DATA_AVAILABLE` 说明（禁止模型编造数值）。
- **后端模块**：`tradingagents/dataflows/interface.py` → `route_to_vendor()`。

### 10.2 SQLite 本地缓存 ✅

- **功能**：行情与指标数据落盘缓存（每标的一个 .db，WAL 模式避免锁冲突），TTL 过期（默认 24h），可强制刷新、按标的/按时间清理。
- **容量上限**：500MB。
- **API**：`POST /api/cache/clear`；`GET /api/cache/stats`。
- **后端模块**：`data_center/cache.py` → `CacheManager`；上层 `DataCenter.get_ohlcv()` 自动"缓存优先、未命中回源"。

---

## 11. API 接口总览

FastAPI 后端（默认 `http://127.0.0.1:8000`），共 30+ 端点：

### 分析流程

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/analyze` | 启动多智能体分析（支持断点恢复） |
| GET | `/api/analyze/{task_id}/stream` | SSE 进度/token 流 |
| GET | `/api/report/{task_id}` | 获取最终报告 |
| GET | `/api/report/{task_id}/sections/{section}` | 分节获取报告 |
| GET | `/api/checkpoints` · `/api/checkpoints/{ticker}` | 断点查询 |

### 行情与图表

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/market-data` | 分析前市场数据包 |
| POST | `/api/chart-data` | K线 + 指标数据 |
| POST | `/api/realtime-prices` | 批量实时报价 |
| WS | `/ws/realtime` | 实时行情推送 |
| POST | `/api/astock-features` | A股特色数据分发（13 项） |

### 交易工具

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/screener` | 条件/模板/自然语言选股 |
| GET | `/api/portfolio` | 持仓汇总 |
| POST | `/api/portfolio/trade` | 模拟下单 |
| GET | `/api/portfolio/history` | 成交记录 |
| GET | `/api/portfolio/nav` | 净值曲线 |
| POST | `/api/portfolio/reset` | 重置账户 |
| POST | `/api/backtest` | 策略/AI 决策回测 📋 |

### 系统与配置

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` · `/api/today` | 健康检查 / 当前交易日 |
| GET/POST | `/api/config` | 运行配置读写 |
| GET | `/api/providers` | LLM 提供商目录 |
| GET | `/api/models/{provider}` | 模型列表（支持代理探测） |
| POST | `/api/cache/clear` · GET `/api/cache/stats` | 缓存管理 |

---

## 12. 通达信功能对照表

| 通达信功能 | 本平台对应 | 状态 |
|-----------|-----------|------|
| K线图（多周期） | TradingViewChart + 13 种周期 | ✅ |
| 分时图 | 实时行情轮询 + 日内分钟K | ⚠️ 无独立分时页面 |
| 技术指标（200+） | 25 种（常用集）+ 参数调整 | ⚠️ 数量少于 TDX，核心指标齐 |
| 画线工具 | 15 种 + 撤销重做 + 样式 | ✅ |
| 智能选股 | 50 字段 × 10 运算符 + 10 模板 | ✅ |
| 定制选股（公式） | 自定义 Filter 组合 | ⚠️ 无公式编辑器 |
| 价格预警 | AlertPanel + 桌面通知 | ✅（本地） |
| 条件预警（指标） | SignalEngine 7 条件（3 求值） | ⚠️ |
| 模拟炒股 | PortfolioPanel + 组合引擎 | ✅ |
| 盘后复盘 | ReplayControls 逐根回放 | ✅ |
| 多窗口看盘 | 1×1 / 1×2 / 2×2 布局 | ✅ |
| 自选股板块 | WatchlistPanel 多分组 | ✅（本地） |
| 筹码分布 | ChipPanel | ✅ |
| 龙虎榜 | DragonTigerPanel | ✅ |
| 北向资金 | NorthboundPanel | ✅ |
| 概念/行业板块 | ConceptPanel | ✅ |
| 盈利预测 | ProfitForecastPanel | ✅ |
| 解禁日历 | LockupPanel | ✅ |
| 人气榜 | HotStockPanel | ✅ |
| 三大报表 | 文本渲染 | ⚠️ |
| 消息面/资讯 | NewsFeed + 新闻智能体 | ✅ |
| 交易下单（实盘） | 无（合规边界，仅模拟） | ❌ 不做 |
| **AI 多智能体研究** | 通达信没有 | ⭐ 本平台独有 |
| **AI 决策回测** | 通达信没有 | ⭐ 本平台独有 |

---

## 13. 已知差距与后续路线

如实列出当前实现与完整愿景之间的差距（按优先级）：

| # | 差距 | 现状 | 方向 |
|---|------|------|------|
| 1 | 回测无 GUI | `POST /api/backtest` 就绪 | 报告页加"回测此决策"按钮 + 结果图表 |
| 2 | 预警条件 3/7 求值 | indicator/cross 4 种已定义未实现 | 补齐 `check_alerts()` 分支 + 后端预警端点 |
| 3 | 自然语言选股为正则解析 | 覆盖常见句式，复杂组合失败 | 接入 LLM 客户端做结构化转换 |
| 4 | `export_image` 占位 | 返回空 bytes | 前端 ECharts 已有截图；后端补 playwright/matplotlib 渲染 |
| 5 | 预警/自选股仅存本地 | localStorage，换设备不同步 | 后端持久化端点 |
| 6 | 分时图缺独立页 | 实时行情 + 分钟K可用 | 1 分针分时走势图（均价线/量） |
| 7 | 指标数量 25 vs TDX 200+ | 常用核心已覆盖 | 按需增量（EXPMA、薛斯通道、神奇九转等） |
| 8 | 行业对比/股东动向/三大报表无面板 | raw markdown 渲染 | 专属可视化面板 |
| 9 | 性能基准测试未建 | 设计文档 §5 目标（渲染<100ms 等） | 补 `test_performance.py` 基准 |

---

*文档基于 2026-08-29 代码库事实编写；全量功能由 1025 个自动化测试覆盖（其中 5 大引擎模块 288 个）。*
