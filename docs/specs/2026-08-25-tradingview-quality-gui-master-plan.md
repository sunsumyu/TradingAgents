# TradingView 级别 GUI 全面开发规划（v2）

> 对标：TradingView / 东方财富 (East Money) / 同花顺 (THS) / 富途牛牛 / 雪球 / Bloomberg Terminal
>
> 创建：2026-08-25 ｜ 更新：2026-08-26
>
> 状态：Phase 0-3 完成；Phase 4 工单 13 张已完成 10 张（01-10），剩余 11/12/13

---

## 1. 项目概述

TradingAgents 是一个基于多 Agent 协作的股票分析系统。当前 GUI 已具备：
- 配置面板（LLM 选择、分析师选择、多平台 LLM 配置）
- 市场数据预览（K 线图 + 6 种技术指标 + 绘图工具 + 分组自选股 + 实时价格）
- 分析进度流式展示（SSE + Token 流）
- 分析报告（Markdown 渲染 + 图表 + 搜索 + 导出）

本文档以 TradingView、东方财富、同花顺为主要标杆，辅以富途牛牛（多图表/盘口）、
雪球（组合管理）、Bloomberg Terminal（预警/命令化操作），系统梳理功能差距，
制定分阶段实施路线图。架构章节使用「深模块/接口/缝合点/适配器」的设计词汇
（deep module / interface / seam / adapter），用于评估每个功能该挂在哪里。

---

## 2. 平台功能对照

### 2.1 图表与行情 (Charting & Market Data)

| 功能 | TradingView | 东方财富 | 同花顺 | 当前状态 | 优先级 |
|------|-------------|---------|--------|---------|--------|
| K 线蜡烛图 | ★★★ | ★★★ | ★★★ | ✅ ECharts 实现 | - |
| 成交量柱状图 | ★★★ | ★★★ | ★★★ | ✅ 已实现 | - |
| MA/EMA 均线叠加 | ★★★ | ★★★ | ★★★ | ✅ MA5/10/20/50 + EMA12/26，IndicatorBar 可切换 | - |
| MACD 指标 | ★★★ | ★★★ | ★★★ | ✅ 副图 | - |
| RSI 指标 | ★★★ | ★★★ | ★★★ | ✅ 副图 | - |
| 布林带 | ★★★ | ★★★ | ★★★ | ✅ 副图 | - |
| KDJ 指标 | ★★ | ★★★ | ★★★ | ✅ 副图（工单04） | - |
| WR / CCI | ★★★ | ★★★ | ★★★ | ✅ 前端计算副图（工单08） | - |
| 资金流向图 | ★ | ★★★ | ★★★ | ✅ FundFlowChart | - |
| 分时图 (Tick) | ★★★ | ★★★ | ★★★ | ❌ 无（并入工单13分钟线） | P3 |
| 多时间周期 | ★★★ (1s~12M) | ★★★ (1min~年) | ★★★ (1min~年) | ✅ 1D~ALL；分钟级见工单13 | P3 |
| 跨周期联动 | ★★★ | ★★ | ★★★ | ❌ 无 | P6 |
| 自定义周期 | ★★★ | ★★ | ★★★ | ❌ 无 | P6 |

### 2.2 交互体验 (Interaction UX)

| 功能 | TradingView | 东方财富 | 同花顺 | 当前状态 | 优先级 |
|------|-------------|---------|--------|---------|--------|
| 十字光标 | ★★★ | ★★★ | ★★★ | ✅ tooltip cross | - |
| 光标数据标签 (O/H/L/C) | ★★★ | ★★★ | ★★★ | ✅ ChartHeader | - |
| Y 轴价格标签（红涨绿跌） | ★★★ | ★★★ | ★★★ | ✅ axisPointer.label（工单03） | - |
| X 轴日期标签 | ★★★ | ★★★ | ★★★ | ✅ 蓝底标签（工单03） | - |
| 鼠标滚轮缩放 / 拖拽平移 | ★★★ | ★★★ | ★★★ | ✅ dataZoom | - |
| 绘图工具栏 | ★★★ | ★★ | ★★★ | ✅ DrawingOverlay | - |
| 趋势线/水平线/矩形/斐波那契 | ★★★ | ★★ | ★★★ | ✅ Canvas overlay | - |
| 撤销/重做 | ★★★ | ★★ | ★★★ | ✅ Ctrl+Z/Y（工单05） | - |
| 图表截图 | ★★★ | ★★ | ★★ | ✅ 含绘图层合成导出（工单06） | - |
| 全屏图表 | ★★★ | ★★ | ★★ | ✅ ESC 退出（工单07） | - |
| K线回放 (Replay) | ★★★ | ❌ | ★★ | ❌ 无 | P6 |
| 多图表布局 | ★★★ | ★★ | ★★ | ❌ 无 | P6 |

### 2.3 自选股与导航 (Watchlist & Navigation)

| 功能 | TradingView | 东方财富 | 同花顺 | 富途 | 当前状态 | 优先级 |
|------|-------------|---------|--------|------|---------|--------|
| 自选股列表 + 点击切换 | ★★★ | ★★★ | ★★★ | ★★★ | ✅ WatchlistPanel | - |
| 实时价格更新 | ★★★ | ★★★ | ★★★ | ★★★ | ✅ 5s HTTP 轮询（工单10） | - |
| WebSocket 推送 | ★★★ | ★★★ | ★★★ | ★★★ | ❌ 工单11 | P3 |
| 价格跳动闪烁动画 | ★★★ | ★★★ | ★★★ | ★★★ | ❌ 工单11 | P3 |
| 分组管理 | ★★★ | ★★★ | ★★★ | ★★★ | ✅ 增删改/折叠/跨组移动（工单09） | - |
| 搜索添加 | ★★★ | ★★★ | ★★★ | ★★★ | ✅ 输入框添加 | - |
| 涨跌颜色（红涨绿跌） | ★★★ | ★★★ | ★★★ | ★★★ | ✅ | - |

### 2.4 技术指标参数 (Indicator Parameters)

| 功能 | TradingView | 东方财富 | 同花顺 | 当前状态 | 优先级 |
|------|-------------|---------|--------|---------|--------|
| 指标参数栏（最新值+颜色） | ★★★ | ★★ | ★★★ | ✅ IndicatorBar（工单02） | - |
| 副图指标切换 | ★★★ | ★★★ | ★★★ | ✅ 6 种指标下拉（工单08） | - |
| MA 参数可调 | ★★★ | ★★★ | ★★★ | ❌ 工单12 | P3 |
| MACD 参数可调 (12/26/9) | ★★★ | ★★ | ★★★ | ❌ 工单12 | P3 |
| RSI 周期可调 | ★★★ | ★★ | ★★★ | ❌ 工单12 | P3 |
| 自定义指标脚本 (Pine) | ★★★ | ❌ | ❌ | ❌ 无 | P6 |

### 2.5 基本面与新闻 (Fundamentals & News)

| 功能 | TradingView | 东方财富 | 同花顺 | 雪球 | 当前状态 | 优先级 |
|------|-------------|---------|--------|------|---------|--------|
| 基本面卡片 | ★★ | ★★★ | ★★★ | ★★★ | ✅ FundamentalCards | - |
| 新闻流 | ★★ | ★★★ | ★★★ | ★★★ | ✅ NewsFeed | - |
| 财务三表 | ★ | ★★★ | ★★★ | ★★ | 后端已实现，GUI 未暴露 | P5 |
| 盈利预测 | ★★ | ★★★ | ★★★ | ★★ | 后端已实现，GUI 未暴露 | P5 |
| 分析师评级 | ★★ | ★★★ | ★★★ | ★★ | ❌ 无 | P6 |
| 股东信息 | ★ | ★★★ | ★★ | ★★ | ❌ 无 | P6 |

### 2.6 A 股特色数据（东方财富数据中心对标）

| 功能 | 东方财富 | 同花顺 | 当前状态 | 优先级 |
|------|---------|--------|---------|--------|
| 龙虎榜 | ★★★ | ★★ | 后端已实现（get_dragon_tiger_board），GUI 未暴露 | P5 |
| 概念板块 | ★★★ | ★★★ | 后端已实现（get_concept_blocks），GUI 未暴露 | P5 |
| 筹码分布 | ★★ | ★★★ | 后端已实现（get_chip_distribution），GUI 未暴露 | P5 |
| 北向资金 | ★★★ | ★★ | 部分（FundFlowChart 历史聚合；get_northbound_flow 未暴露） | P5 |
| 解禁数据 | ★★★ | ★★ | 后端已实现（get_lockup_expiry），GUI 未暴露 | P5 |
| 行业资金排名 | ★★★ | ★★ | 后端已实现（get_industry_comparison），GUI 未暴露 | P5 |
| 人气榜/热门股 | ★★★ | ★★ | 后端已实现（get_hot_stocks），GUI 未暴露 | P5 |
| 内部人交易 | ★★ | ★ | 后端已实现（get_insider_transactions），GUI 未暴露 | P5 |

> 这一行是本规划最大的杠杆点：上述能力在 `tradingagents/dataflows/a_stock.py`
> 中已经全部实现并经过多 Agent 投研场景的实战验证，只缺「薄 API 端点 + GUI
> 面板」这一层展示。详见第 6 节 Phase 5 提案。

### 2.7 进阶功能（预警/选股/组合 - TradingView/富途/雪球对标）

| 功能 | TradingView | 东方财富 | 富途 | 雪球 | Bloomberg | 当前状态 | 优先级 |
|------|-------------|---------|------|------|-----------|---------|--------|
| 价格预警 | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ | ❌ 无（本地后端+轮询基建已就绪） | P5 |
| 选股器/筛选 | ★★★ | ★★★ | ★★ | ★★ | ★★★ | ❌ 无（可联动 AI：自然语言选股） | P5 |
| 模拟组合 | ★★★ | ★★ | ★★★ | ★★★ | ★★ | ❌ 无 | P6 |
| K线回放 | ★★★ | ❌ | ★★ | ❌ | ❌ | ❌ 无 | P6 |
| 多图表布局 | ★★★ | ★★ | ★★★ | ❌ | ★★★ | ❌ 无 | P6 |
| 盘口五档/L2 | ❌(付费) | ★★★ | ★★★ | ★ | ★★★ | ❌ 无 | P6 |

### 2.8 AI 分析报告（独有优势，无对标）

| 功能 | 当前状态 |
|------|---------|
| 多 Agent 协作分析 | ✅ 核心差异化 |
| 实时进度流 + Token 流式输出 | ✅ SSE |
| 分析师报告 Tab / 信号仪表盘 / 目录导航 | ✅ |
| 报告搜索 (Ctrl+F) / 导出 (MD/HTML/JSON) / 打印 / 断点续传 | ✅ |

---

## 3. 代码架构与模块设计

> 本节用「深模块/接口/缝合点/适配器」的设计词汇评估现状。深模块 = 小接口背后
> 藏大量行为；调用者学得少、得到的多（leverage），变更集中在实现内部（locality）。

### 3.1 前端组件树

```
App.tsx                           # Phase 状态机: config -> market_data -> analyzing -> report
├── TopBar                        # 后端状态指示灯 + 连接测试
├── ConfigPanel                   # LLM 多平台配置 / 分析师选择 / 深度
├── ProgressPanel                 # SSE 进度流 + Token 流式输出
├── MarketDataPanel               # 市场数据预览入口
│   ├── TradingViewLayout         # TradingView 风格完整布局
│   │   ├── ChartHeader           # 标的名称 + 实时价格 + 涨跌 + OHLCV
│   │   ├── TimeframeSelector     # 1D~ALL 周期切换（分钟级见工单13）
│   │   ├── IndicatorBar          # 指标参数栏：MA/EMA 切换 + 最新值 + 颜色编码
│   │   ├── DrawingToolbar        # 趋势线/水平线/矩形/斐波那契工具栏
│   │   ├── TradingViewChart      # ECharts K线主图 + axisPointer 轴标签
│   │   │   └── DrawingOverlay    # Canvas 绘图层（撤销/重做/resetKey 清空）
│   │   ├── SubPanels             # 3 槽位副图 × 6 种指标可切换
│   │   │   └── SubPanelHeader    # 每槽位指标下拉（无数据置灰）
│   │   └── WatchlistPanel        # 分组自选股 + 实时价格合并渲染
│   ├── FundamentalCards          # PE/PB/EPS/市值等基本面卡片
│   └── NewsFeed                  # 新闻流列表
├── ReportPanel                   # 分析报告（搜索/TOC/导出/打印）
└── ErrorBoundary                 # 全局错误边界
```

### 3.2 后端 API 端点

| 端点 | 方法 | 用途 | 请求体 |
|------|------|------|--------|
| `GET /` | GET | 健康检查 | - |
| `GET /api/today` | GET | 服务端日期 | - |
| `GET /api/providers` | GET | LLM 提供商列表 | - |
| `GET /api/models/{provider}` | GET | 模型列表 | query: proxy_url, api_key |
| `POST /api/analyze` | POST | 启动分析 | AnalyzeRequest |
| `GET /api/report/{task_id}` | GET | 获取报告 | - |
| `GET /api/analyze/{task_id}/stream` | SSE | 进度流 + Token流 | - |
| `POST /api/market-data` | POST | 市场数据预览 | { ticker, date } |
| `POST /api/chart-data` | POST | 图表数据 | { ticker, date, days } |
| `POST /api/realtime-prices` | POST | 批量实时行情（轮询） | { tickers[] } |
| `GET /api/config` / `POST /api/config` | GET/POST | YAML 配置读写 | config object |
| `GET /api/checkpoints/{ticker}` | GET | 检查断点续传 | - |

### 3.3 数据模型

```
MarketDataResponse
├── kline: KlineData              # OHLCV + MA/EMA/KDJ
├── macd / rsi / bollinger        # 副图指标
├── fund_flow: FundFlowData       # 北向/主力/散户资金流
├── fundamentals: FundamentalsData
└── news: NewsItem[]

RealtimePriceItem（工单10 新增）
├── price / change / changePct
└── name (A股中文名，腾讯行情带回)

WatchlistGroup（工单09 新增，localStorage: tradingagents_watchlist_groups）
├── id / name / collapsed
└── items: WatchlistItem[]
```

### 3.4 深模块清单（各功能的杠杆所在）

**`fetch_realtime_prices(tickers) -> dict[str, RealtimePriceItem]`**（`tradingagents_api/realtime.py`）
- 接口：一个函数、一个参数。调用者（server.py 端点）不感知任何路由细节。
- 实现隐藏：A 股/非 A 股判定、腾讯批量 vs yfinance 并发（线程池上限 8）、
  去重、单标的失败隔离、停牌代码缺席（不产出僵尸价格）。
- 杠杆：HTTP 轮询端点、未来的 WebSocket 端点、CLI 都复用同一实现。

**`useRealtimePrices(tickers, enabled) -> Map<string, RealtimePrice>`**（前端 Hook）
- 接口：两参数一返回值。
- 实现隐藏：轮询生命周期、AbortController、静默降级（保留上次快照）、
  Map 身份稳定性（仅在有新数据时变化，避免每 5s 空 re-render）。
- 杠杆：工单11 升级 WebSocket 时**接口不变、只换实现内部**，WatchlistPanel
  一行不改。

**`loadWatchlistGroups() / saveWatchlistGroups(groups)`**（`watchlist-store.ts`）
- 缝合点：WatchlistPanel 只依赖这对 load/save，不感知 localStorage。
- 旧版平铺数据迁移、损坏 JSON 回退都藏在实现里。
- 未来迁移到后端持久化（多设备同步）时只换 adapter。

**`chart-utils.ts` 指标单一事实源**
- `OVERLAY_INDICATORS`（叠加指标配置）、`computeWR/computeCCI`（纯前端计算）、
  `buildOverlaySeries`（ECharts 序列构造）。
- 报告页 KlineChart 与 TradingView 主图共享同一配置——改一处两处生效。

**`SubIndicatorPanel` 副图指标分发**
- 接口：`indicator: SubIndicatorKey + 数据 props -> ReactNode`。
- 6 个 Mini 适配器（Macd/Rsi/Bollinger/Kdj/Wr/Cci）各自满足同一形状。
- 加新指标 = 加一个 case + 一个 Mini 组件，布局代码不动。

### 3.5 缝合点与适配器

| 缝合点 | 活跃适配器 | 休眠适配器 | 说明 |
|--------|-----------|-----------|------|
| 绘图层 | DrawingOverlay（ECharts Canvas overlay） | DrawingManager.ts（lightweight-charts IPanePrimitive） | 一个适配器 = 假想缝合点；只有真正迁移图表引擎（第二个适配器激活）这条缝才实。保留作迁移路标 |
| Watchlist 持久化 | localStorage（watchlist-store.ts） | 无（可加后端 API adapter） | |
| 实时行情传输 | HTTP 轮询（useRealtimePrices） | 无（工单11 将加 WebSocket adapter） | Hook 接口已为双适配器做好准备 |
| 行情数据源路由 | fetch_realtime_prices（腾讯/yfinance 双路） | - | 已经是双适配器结构 |

### 3.6 浅模块与技术债

- **TradingViewLayout.tsx 仍在膨胀**（~750 行）：SubPanels + 4 个 Mini 组件
  还内联在文件尾部。按既定拆分建议（第 8.3 节）移出到独立文件是下一个
  重构动作；不紧急但每次改副图都在变差。
- **两套颜色方案并存**：KlineChart 历史方案（MA5=#F7B731…）与 chart-theme
  方案（ma5=#2962FF…）。工单01 的提取刻意保持了行为不变，未统一。统一
  需要一次性视觉决策，放到 Phase 4 收尾后做。
- **前端零测试**：WR/CCI 计算已用脚本数值验证（.scratch/verify_wr_cci.mjs），
  但没有固化为可回归的测试。见第 11 节。

---

## 4. 已完成阶段记录

### Phase 0: K 线图数据修复 ✅

**问题**：A 股标的 (600733) 显示"暂无K线数据"

**根因链路**：`route_to_vendor` 配置只含 yfinance（不支持 A 股）→ a_stock
从未被调用；且 mootdx 探测 38 个服务器 × 2s 超时；CSV 解析器要求 7 列但
a_stock 返回 6 列。

**修复**：`a_stock.py` 加 8 秒全局探测截止 + 单次调用线程超时；
`chart_data.py` 中 A 股（6 位数字代码）直接路由到 a_stock 绕过 vendor chain、
CSV 解析器兼容 6/7 列。

### Phase 1: 时间周期切换 ✅

`api.getChartData()` + AbortSignal；`handleTimeframeChange` 取消旧请求防竞态；
加载遮罩 + 可关闭的错误 toast。

### Phase 2: 功能补全 ✅

Watchlist 点击切换标的（ticker 从 prop 提升为 state）；Canvas overlay 绘图
工具（趋势线/水平线/矩形/斐波那契，crosshair 模式事件穿透）。

### Phase 3: 体验提升 ✅（工单 01-07）

| 工单 | 交付物 |
|------|--------|
| 01 | `chart-utils.ts` 指标配置单一事实源（KlineChart 与主图共享） |
| 02 | `IndicatorBar` 指标参数栏：点击 toggle、最新值实时显示、颜色编码 |
| 03 | 十字光标 Y 轴价格标签（背景色按光标价 vs 最新收盘红涨绿跌）+ X 轴日期蓝底标签 |
| 04 | KDJ 副图：K/D/J 三线 + 80/20 参考线 + 与主图光标联动 |
| 05 | 绘图撤销/重做：Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z，双栈 useRef（50 步上限），双击清空可撤销，resetKey 切标的自动清空 |
| 06 | 截图导出：DOM canvas 合成（ECharts 层 + 绘图层），2×DPR 输出，`{ticker}_chart_{date}.png` |
| 07 | 全屏图表模式：隐藏 Watchlist/副图，ESC 退出，截图在全屏下同样可用 |

### Phase 4: 高级功能 🔄（工单 08-13，已完成 10 张）

| 工单 | 交付物 | 状态 |
|------|--------|------|
| 08 | 副图指标切换：3 槽位 × 6 种指标下拉，WR(14)/CCI(20) 前端纯计算（合成数据数值验证通过），槽位选择 localStorage 持久化，互换语义 | ✅ |
| 09 | 自选股分组：默认组「自选股」+ 增删改/折叠/跨组移动（去重），旧平铺数据自动迁移 | ✅ |
| 10 | 实时价格轮询：`POST /api/realtime-prices`（A 股腾讯批量 + 美股 yfinance fast_info 并发），前端 5s 轮询 Hook，静默降级。实测 600519/000001/AAPL 混合请求全部正确 | ✅ |
| 11 | WebSocket 升级 + 价格跳动动画 | 待做 |
| 12 | 技术指标参数可调 | 待做 |
| 13 | 分钟级时间周期（1/5/15/30/60min） | 待做 |

---

## 5. 剩余工单规格（11/12/13）

### 5.1 工单11 - WebSocket 升级 + 价格跳动动画

- 后端 `ws://127.0.0.1:8420/ws/realtime`：客户端发标的列表，服务端 3s 周期推送
  （复用 `fetch_realtime_prices` 深模块——端点只是传输层换了个 adapter）。
- 前端 `useRealtimePrices` 内部优先 WebSocket，onerror/onclose 降级回 HTTP
  轮询，断线 5s 重连；**对外接口不变**。
- ChartHeader 价格变动时红/绿背景闪烁一次（约 1s 淡出），Watchlist 数据源
  无缝切换不闪断。

### 5.2 工单12 - 技术指标参数可调

- MA（4 个周期）/MACD（快慢信号 12/26/9）/RSI（周期 14）参数弹窗，
  输入校验（正整数、合理范围）。
- 确定后**前端基于当前 K 线重算**，无需重新请求；重置默认按钮。
- 参数 localStorage 持久化；前端重算与后端默认参数抽样对比误差 < 0.01。

### 5.3 工单13 - 分钟级时间周期

- `chart-data` 接口支持分钟粒度：A 股走 mootdx 分钟线，美股走 yfinance
  interval（注意单次范围限制）。
- 周期选择器加 1/5/15/30/60min 按钮；切换/加载/竞态取消与日级一致。
- 指标（MA/MACD/RSI/Boll/KDJ/WR/CCI）按分钟序列计算且与数据对齐。

---

## 6. Phase 5 提案：A 股特色数据中心（唤醒沉睡的后端深模块）

> 这是「杠杆」的最佳案例：`tradingagents/dataflows/a_stock.py` 已实现一批
> 东方财富数据中心级功能，接口都很窄（代码/日期入，结构化数据出），经过了
> 多 Agent 投研实战验证。每个功能从后端就绪到 GUI 可见，只差「薄 API 端点 +
> Pydantic 模型 + 一个面板组件」，工作量约为全新功能的 1/3。

| 后端函数 | 对标产品功能 | GUI 形态提案 |
|---------|------------|------------|
| `get_dragon_tiger_board` | 东财数据中心-龙虎榜 | 表格面板：上榜日/原因/买卖席位/净买入额 |
| `get_concept_blocks` | 东财/同花顺-概念板块 | 板块涨幅排行 + 点击板块看成分股 |
| `get_chip_distribution` | 同花顺-筹码分布（招牌功能） | 横向成本分布图 + 获利比例 |
| `get_northbound_flow` | 东财-北向资金 | 时间序列图（现有 FundFlowChart 扩展实时口径） |
| `get_hot_stocks` | 东财-人气榜 | 侧栏热门股列表（一键加自选） |
| `get_profit_forecast` | 同花顺-盈利预测 | 基本面区预测卡片（EPS 预测/机构数） |
| `get_lockup_expiry` | 东财-解禁数据 | 解禁日历/时间线 |
| `get_industry_comparison` | 东财-行业资金排名 | 行业热度条形图 |
| `get_insider_transactions` | 美股内部人交易 | 报告页补充面板 |
| `get_balance_sheet` / `get_cashflow` / `get_income_statement` | 东财-财务三表 | 财务 Tab（三张报表切换） |

**实施要点**：
- 新端点建议合并为 `POST /api/astock-features`（feature 名 + ticker/date 参数），
  而不是每功能一个端点——保持接口面小。
- 面板挂在 MarketDataPanel 下方 Tab 区（「行情 | 资金 | 龙虎榜 | 筹码 | 财务」）。
- 同花顺筹码分布是 A 股用户的肌肉记忆，优先级最高；龙虎榜次之。
- 与 AI 分析天然联动：这些面板数据可作为 analyst 的输入上下文（长期方向）。

---

## 7. Phase 6 展望：交易员级工具

| 功能 | 对标 | 本项目切入点的独特优势 |
|------|------|----------------------|
| **价格预警** | TradingView 告警 / Bloomberg MON | 本地常驻后端（granian）+ `fetch_realtime_prices` 已就绪，加一个后台检查循环 + Tauri 系统通知即可，无云端成本 |
| **自然语言选股器** | 同花顺问财 / TradingView Screener | 独有优势：LLM 前置——「帮我找北向连续加仓且 PE<20 的消费股」直接翻译成对 Phase 5 数据函数的组合调用 |
| **K线回放** | TradingView Replay | 对 AI 分析尤有价值：回放历史某天，让 Agent 只看到当日及之前的数据做「穿越测试」 |
| **多图表布局** | 富途 4 图 / TradingView 多窗 | Tauri 多窗口或单页 grid，KlineData 模型已就绪 |
| **模拟组合** | 雪球组合 | 与 AI 信号联动：报告的 Buy/Sell 建议自动生成调仓记录 |
| **盘口五档/L2** | 富途/东财 Level-2 | 数据源需另行接入（腾讯/东财 L2 接口），成本最高，最后做 |

---

## 8. 架构改进方向

### 8.1 图表引擎迁移路线

| 阶段 | 目标 | 状态 |
|------|------|------|
| 当前 | ECharts + Canvas overlay + 指标参数栏 | ✅ |
| Phase 4 | ECharts + WebSocket 实时 + 分钟线 | 🔄 |
| Phase 5+ | 视需求评估 lightweight-charts 迁移 | 📋 |

**暂不迁移 lightweight-charts 的理由**：ECharts 在 Tauri WebView2 已验证稳定；
tooltip/dataZoom/markLine 开箱即用；A 股特色（涨跌停色、资金流、筹码分布）
都需要自定义渲染；Canvas overlay 已解决绘图需求；迁移成本高收益不确定。
DrawingManager.ts 作为该缝合点上的休眠适配器保留。

### 8.2 状态管理改进（Zustand，渐进式）

```
store/
├── useChartStore.ts      # ticker, kline, macd, rsi, bollinger, timeframe, activeOverlays
├── useWatchlistStore.ts  # groups, addItem, moveItem, collapse
├── useRealtimeStore.ts   # prices Map + 传输模式（polling/ws）
├── useAnalysisStore.ts   # config, phase, events, report, streamingText
├── useDrawingStore.ts    # activeTool, drawings, undo, redo
└── useUIStore.ts         # isFullscreen, subpanelSlots, tocWidth
```

### 8.3 组件拆分建议（TradingViewLayout 瘦身）

```
tradingview/
├── TradingViewLayout.tsx      # 主布局容器（目标 ~200 行）
├── IndicatorBar.tsx           # ✅ 已独立
├── SubPanelHeader.tsx         # ✅ 已独立
├── SubIndicatorMinis.tsx      # ✅ WrMini/CciMini；待迁入：Macd/Rsi/Bollinger/Kdj Mini
├── WatchlistPanel.tsx + watchlist-store.ts  # ✅ 已分离持久化
└── ...（其余保持现状）
```

---

## 9. 实施路线图

### Phase 0-2: 数据修复 + 核心交互 ✅
### Phase 3: 体验提升 ✅（工单 01-07）
### Phase 4: 高级功能 🔄（当前）
- [x] 副图指标切换 + WR/CCI（工单08）
- [x] 自选股分组管理（工单09）
- [x] 实时价格轮询 v1（工单10）
- [ ] WebSocket 升级 + 价格跳动动画（工单11）
- [ ] 技术指标参数可调（工单12）
- [ ] 分钟级时间周期（工单13）

### Phase 5: A 股特色数据中心 📋（提案，见第 6 节）
- [ ] 筹码分布面板（同花顺对标，优先）
- [ ] 龙虎榜面板
- [ ] 概念板块热力图
- [ ] 财务三表 Tab + 盈利预测卡片
- [ ] 北向资金实时口径 + 解禁日历
- [ ] 价格预警（本地后端 + Tauri 通知）
- [ ] TradingViewLayout 瘦身重构（8.3 节）

### Phase 6: 交易员级工具 📋（展望，见第 7 节）
- [ ] 自然语言选股器（AI 联动，独有优势）
- [ ] K线回放（AI 穿越测试）
- [ ] 多图表布局 / 模拟组合 / 盘口 L2

---

## 10. 性能优化清单

### 已实施

| 优化项 | 方法 | 效果 |
|--------|------|------|
| mootdx 探测 | 8s 全局截止 + max_probe=15 | 70s → 8s |
| 周期/标的切换 | AbortController 竞态取消 | 无过期数据渲染 |
| ECharts 渲染 | `animation:false` + `notMerge` | 减少动画开销 |
| 实时行情轮询 | Map 身份稳定 + 单请求合并 | ≤1 次 re-render / 5s |
| yfinance 并发 | 线程池上限 8 | 不会打爆 Yahoo 限流 |
| 东财防封 | `_em_get` 全局限流 + Keep-Alive（a_stock 既有） | 多 Agent 批量不被封 IP |

### 待实施

| 优化项 | 方法 | 优先级 |
|--------|------|--------|
| 图表虚拟化 | >1000 bars 仅渲染可见区域 | P4 |
| 指标计算缓存 | 相同参数不重算（工单12 前置） | P3 |
| Watchlist 虚拟滚动 | >100 条虚拟列表 | P5 |
| WebSocket 连接复用 | 多面板共享一条连接 | P3（工单11） |

---

## 11. 测试策略

### 已有
- `tests/test_astock_review_fixes.py` / `test_multi_platform_llm.py` / `test_progress_callback.py`
- WR/CCI 公式合成数据数值验证（.scratch 脚本，**待固化为正式测试**）

### 建议新增

| 类型 | 内容 | 工具 |
|------|------|------|
| 单元 | `computeWR/computeCCI` 边界（warmup null / 平坦窗口 / 已知值） | vitest |
| 单元 | `fetch_realtime_prices` 路由判定（mock 腾讯/yfinance） | pytest |
| 单元 | watchlist-store 迁移逻辑（旧平铺 → 分组） | vitest |
| 集成 | `/api/realtime-prices` 混合标的端到端 | httpx + pytest |
| E2E | 副图切换 / 分组操作 / 参数弹窗 | Playwright |
| E2E | 周期快速连点竞态（不出现过期渲染） | Playwright |

---

## 12. 参考资源

### TradingView
- https://www.tradingview.com/ ｜ https://tradingview.github.io/lightweight-charts/
- 设计语言：深色 #131722、强调 #2962FF、涨 #089981、跌 #F23645

### 东方财富
- https://quote.eastmoney.com/ ｜ https://data.eastmoney.com/（数据中心，Phase 5 主对标）
- 特点：红涨绿跌、资金流向、龙虎榜、北向、Level-2

### 同花顺
- https://www.10jqka.com.cn/ ｜ http://data.10jqka.com.cn/
- 特点：50+ 指标、筹码分布（招牌）、问财自然语言选股、多周期联动

### 富途牛牛 / 雪球 / Bloomberg
- https://www.futunn.com/（多图表布局、盘口、社区）
- https://xueqiu.com/（组合管理、讨论氛围）
- Bloomberg Terminal（MON 监控、预警、命令化操作的极致范式）

### 技术
- ECharts 6 ｜ Pydantic v2 ｜ Tauri 2 ｜ granian ASGI

---

## 13. 文件变更清单

### Phase 3-4 新增代码
| 文件 | 用途 | 工单 |
|------|------|------|
| `tradingagents_gui/src/lib/chart-utils.ts` | 指标配置单一事实源 + WR/CCI 前端计算 | 01/08 |
| `tradingagents_gui/src/components/tradingview/IndicatorBar.tsx` | 指标参数栏 | 02 |
| `tradingagents_gui/src/components/tradingview/SubPanelHeader.tsx` | 副图指标下拉 | 08 |
| `tradingagents_gui/src/components/tradingview/SubIndicatorMinis.tsx` | WrMini/CciMini | 08 |
| `tradingagents_gui/src/components/tradingview/watchlist-store.ts` | 分组持久化 + 迁移 | 09 |
| `tradingagents_gui/src/lib/useRealtimePrices.ts` | 实时价格轮询 Hook | 10 |
| `tradingagents_api/realtime.py` | 批量实时行情（腾讯/yfinance 双路） | 10 |
| `.scratch/tradingview-phase34/issues/01-13` | 工单追踪 | 全部 |

### Phase 3-4 修改
| 文件 | 变更 | 工单 |
|------|------|------|
| `TradingViewLayout.tsx` | 周期/标的状态 + 截图 + 全屏 + 副图槽位 | 01-10 |
| `TradingViewChart.tsx` | activeOverlays/activeTool props + axisPointer 轴标签 | 02/03/05 |
| `DrawingOverlay.tsx` | 撤销/重做 + resetKey | 05/06 |
| `WatchlistPanel.tsx` | 分组重构 + 实时价格合并 | 09/10 |
| `types.ts` | WatchlistGroup / RealtimePrice | 09/10 |
| `api.ts` / `types.ts`（lib） | getRealtimePrices / RealtimePrice | 10 |
| `a_stock.py` | get_realtime_quotes 公开批量行情入口 | 10 |
| `schemas.py` / `server.py` | RealtimePriceRequest/Item + 端点 | 10 |

### 规格文档
| 文件 | 用途 |
|------|------|
| `2026-08-25-tradingview-quality-gui-master-plan.md` | 主规划（本文档 v2） |
| `2026-08-25-phase3-*.md` ×3 | Phase 3 详细规格 |
| `2026-08-25-phase4-realtime-watchlist-api-design.md` | Phase 4 API 设计 |
| `2026-08-25-performance-testing-strategy.md` | 性能 + 测试策略 |

### 保留未连接
| 文件 | 状态 |
|------|------|
| `DrawingManager.ts` | 休眠适配器（lightweight-charts 绘图），迁移路标 |
