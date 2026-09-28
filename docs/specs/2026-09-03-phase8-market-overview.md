# Phase 8 规格：市场全景图（对标通达信「市场」视图）

> 对标：通达信「市场」→「全景图」页面
>
> 日期：2026-09-03 ｜ 状态：提案
>
> 前置：Phase 5（A股特色数据中心）+ Phase 7（交易员数据中心增强）
>
> 参考截图：通达信 TdxW 2026-09-03 18:22 全景图
>
> **[2026-09-27 指向]** 本规格已并入并裁决于
> [`2026-09-27-eastmoney-aligned-platform-plan.md`](2026-09-27-eastmoney-aligned-platform-plan.md)
> （Phase 10–12）。原文保留，作为功能细节来源。

---

## 1. Problem Statement

TradingAgents 当前缺少一个**市场全局概览页面**。用户在启动平台后，需要快速了解：

- 三大指数（上证/深证/创业板）今日走势如何？
- 哪些股票涨幅最大？哪些跌幅最大？
- 哪些行业/概念板块在领涨？
- 市场整体涨跌家数、成交额如何？
- 最新市场资讯是什么？

当前用户需要逐个打开个股图表、查看不同数据面板才能拼凑出市场全貌，效率低下。通达信的「市场→全景图」页面将所有这些信息集中在一个视图中，TradingAgents 需要对标实现。

---

## 2. Solution

新增一个**市场全景图（Market Overview）**独立页面，作为平台的"首页仪表盘"。页面分为四个区域：

```
┌──────────────────────────────────────────────────────────────────┐
│  [指数分时图 × 3]  上证指数  │  深证成指  │  创业板指              │
├──────────────┬──────────────┬────────────────────────────────────┤
│  上证A股      │  深证A股      │  板块排行                         │
│  涨幅 Top10   │  涨幅 Top10   │  [全部][行业][概念][风格][地区]     │
│  跌幅 Top10   │  跌幅 Top10   │  排行表（代码/名称/涨幅/现价/…）    │
├────────────────────────────┴────────────────────────────────────
│  24小时滚动资讯              │  个股分时图（点击股票后显示）        │
├─────────────────────────────┴────────────────────────────────────
│  状态栏：总成交额 | 上涨 N 家 | 下跌 N 家 | 平盘 N 家              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. User Stories

1. 作为交易员，我希望打开平台就能看到三大指数的分时走势图，以便快速判断大盘方向
2. 作为交易员，我希望看到上证A股涨幅前10的股票列表，以便发现强势股
3. 作为交易员，我希望看到上证A股跌幅前10的股票列表，以便规避风险
4. 作为交易员，我希望看到深证A股涨跌幅排行，与上证形成对比
5. 作为交易员，我希望按行业/概念/风格/地区切换板块排行表，以便发现领涨板块
6. 作为交易员，我希望板块排行表显示涨幅%、现价、涨跌额、涨速%、量比、涨跌数、涨停数，以便全面评估板块强度
7. 作为交易员，我希望点击板块排行中的某个板块，能查看该板块的成分股
8. 作为交易员，我希望点击涨幅/跌幅列表中的股票，能在右侧显示该股票的分时图
9. 作为交易员，我希望看到24小时滚动市场资讯，以便了解最新动态
10. 作为交易员，我希望在底部状态栏看到市场总成交额、上涨/下跌/平盘家数，以便判断市场情绪
11. 作为交易员，我希望所有数据自动刷新（指数/行情每30秒，新闻每60秒），无需手动刷新
12. 作为交易员，我希望板块排行表可以点击表头排序（涨幅/现价/量比等）

---

## 4. Implementation Decisions

### 4.1 后端模块

**新文件**：`tradingagents/dataflows/a_stock/market_overview.py`

```
get_index_trends(index_codes: list[str]) -> dict
    # 三大指数分时数据
    # 使用 push2 trends2 API
    # 返回：{ code: { name, pre_close, trends: [{time, price, avg_price, volume}] } }

get_stock_ranking(market: str, sort: str = "gain", limit: int = 10) -> list[dict]
    # 涨幅/跌幅排行
    # market: "sh" (上证A股) | "sz" (深证A股)
    # sort: "gain" (涨幅降序) | "loss" (涨幅升序)
    # 使用 push2 clist API
    # 返回：[{ code, name, price, change_pct, change, volume, amount }]

get_board_ranking(board_type: str, sort: str = "change_pct", limit: int = 50) -> list[dict]
    # 板块排行
    # board_type: "industry" | "concept" | "style" | "region" | "all"
    # 使用 push2 clist API（不同 fs 参数区分板块类型）
    # 返回：[{ code, name, change_pct, price, change, speed, volume_ratio, up_count, down_count, limit_up_count }]

get_market_breadth() -> dict
    # 市场宽度统计
    # 返回：{ total, up_count, down_count, flat_count, total_amount_yi }

get_market_news(limit: int = 30) -> list[dict]
    # 复用现有 CLS + Eastmoney 新闻获取逻辑
    # 返回：[{ title, content, time, source }]
```

**新 API 端点**：`GET /api/market-overview`

```json
{
  "indices": {
    "000001": { "name": "上证指数", "price": 3942.09, "change_pct": 0.02, "trends": [...] },
    "399001": { "name": "深证成指", "price": 13625.12, "change_pct": 0.10, "trends": [...] },
    "399006": { "name": "创业板指", "price": 3312.54, "change_pct": 0.01, "trends": [...] }
  },
  "sh_gainers": [...],
  "sh_losers": [...],
  "sz_gainers": [...],
  "sz_losers": [...],
  "boards": {
    "industry": [...],
    "concept": [...]
  },
  "breadth": { "total": 5556, "up": 920, "down": 1937, "flat": 2699, "amount_yi": 17805 },
  "news": [...]
}
```

**设计理由**：
- 单一端点返回全部数据，前端一次请求即可渲染整个页面
- 后端内部并行请求各数据源（asyncio.gather），总延迟 = 最慢的一个接口
- 复用现有 `http_client.default_client`（已绕过系统代理）
- 缓存策略：指数/行情数据缓存 30 秒，板块数据缓存 60 秒，新闻缓存 5 分钟

### 4.2 数据源映射

| 数据 | 接口 | fs 参数 | 说明 |
|------|------|---------|------|
| 指数分时 | push2 trends2 | secid=1.000001 | 上证/深证/创业板 |
| 上证A股排行 | push2 clist | `m:1 t:2,m:1 t:23` | 上证主板+科创板 |
| 深证A股排行 | push2 clist | `m:0 t:6,m:0 t:80` | 深证主板+创业板 |
| 行业板块 | push2 clist | `m:90 t:2 f:!50` | 496 个行业 |
| 概念板块 | push2 clist | `m:90 t:3 f:!50` | 504 个概念 |
| 风格板块 | push2 clist | `m:90 t:4 f:!50` | 风格分类 |
| 地区板块 | push2 clist | `m:90 t:5 f:!50` | 地区分类 |
| 市场宽度 | push2 clist + filter | 全A股 fs | 涨跌家数统计 |
| 新闻 | CLS + Eastmoney | 已有 | 复用 Phase 5 新闻模块 |

### 4.3 前端组件

**新文件**：`tradingagents_gui/src/components/market/MarketOverviewPage.tsx`

布局结构：
```
MarketOverviewPage
├── IndexChartsRow           # 三大指数分时图（ECharts line chart × 3）
├── RankingSection
│   ├── StockRankingPanel    # 上证A股涨跌幅（左）
│   ├── StockRankingPanel    # 深证A股涨跌幅（中）
│   └── BoardRankingTable    # 板块排行表（右，含 Tab 切换）
├── NewsAndChartSection
│   ├── NewsFeed             # 24小时滚动资讯（复用/扩展现有 NewsFeed）
│   └── MiniChart            # 个股分时图（点击股票后显示）
└── MarketStatusBar          # 底部状态栏（成交额/涨跌家数）
```

**关键交互**：
- 指数分时图：ECharts 折线图 + 量能柱，30 秒自动刷新
- 涨跌幅列表：点击股票 → 右侧 MiniChart 显示该股票分时图
- 板块排行表：Tab 切换（行业/概念/风格/地区），点击表头排序，点击板块 → 显示成分股
- 新闻列表：自动滚动，60 秒刷新
- 全部组件懒加载，页面打开时一次性请求 `GET /api/market-overview`

### 4.4 路由与入口

- **路由**：`/market` — 独立页面，不在现有图表页内
- **入口**：TopBar 导航栏新增「市场」按钮，点击跳转到 `/market`
- **与现有页面关系**：独立页面，不嵌入现有图表页（信息密度太高，嵌入会导致拥挤）

### 4.5 性能考量

- 后端并行请求 6-8 个数据源接口，使用 `asyncio.gather`
- 预计总延迟：3-5 秒（受限于最慢的接口）
- 前端缓存响应数据 30 秒，避免频繁刷新
- 指数分时图数据量大（241 点 × 3 指数），单独缓存

---

## 5. Testing Decisions

### 5.1 后端测试

- **快照测试**：每个数据获取函数基于真实 API 输出写快照测试（类似 Phase 5 解析器测试模式）
- **接口测试**：`GET /api/market-overview` 返回完整 JSON 结构，验证所有字段存在
- **并发测试**：验证 `asyncio.gather` 并行请求不触发东财限流
- **缓存测试**：验证 30 秒内重复请求命中缓存

### 5.2 前端测试

- **组件渲染测试**：每个子组件（IndexChartsRow, StockRankingPanel, BoardRankingTable 等）独立测试
- **交互测试**：点击股票 → MiniChart 更新；Tab 切换 → 数据更新
- **ECharts 初始化测试**：指数分时图正确渲染

### 5.3 参考现有测试

- 后端：参考 `tests/test_astock_features.py` 的快照测试模式
- 前端：参考 `tradingagents_gui/src/components/astock/` 下各 Panel 的测试

---

## 6. Out of Scope

以下功能不在 Phase 8 范围内，留待后续迭代：

| 功能 | 原因 | 后续 |
|------|------|------|
| 期货/期权行情 | 截图有「期货现货」Tab，但本次只做 A 股 | Phase 9 |
| 港股/美股行情 | 截图左侧有「港股行情」「美股/海外」 | Phase 9 |
| 债券行情 | 截图左侧有「债券行情」 | Phase 9 |
| 板块成分股详情 | 点击板块后显示成分股列表 | Phase 8.1 后续 |
| 自定义布局 | 用户拖拽调整各区域大小 | Phase 10 |
| 历史日期回溯 | 查看历史某天的全景图 | Phase 10 |
| WebSocket 实时推送 | 当前用轮询，后续可改为 WS 推送 | Phase 9 |

---

## 7. 工单拆分

| 工单 | 内容 | 依赖 | 预估 |
|------|------|------|------|
| 8.01 | 后端：`market_overview.py` 数据模块（指数/排行/板块/宽度/新闻） | - | 1.5d |
| 8.02 | 后端：`GET /api/market-overview` 端点 + 缓存 | 8.01 | 0.5d |
| 8.03 | 前端：IndexChartsRow（三大指数分时图） | 8.02 | 1d |
| 8.04 | 前端：StockRankingPanel（涨跌幅列表 × 2） | 8.02 | 0.5d |
| 8.05 | 前端：BoardRankingTable（板块排行 + Tab 切换） | 8.02 | 1d |
| 8.06 | 前端：NewsFeed + MiniChart + MarketStatusBar | 8.02 | 0.5d |
| 8.07 | 前端：MarketOverviewPage 总装 + 路由 + TopBar 入口 | 8.03-8.06 | 0.5d |
| 8.08 | 测试 + 性能优化 | 全部 | 0.5d |

**总计**：约 6 个工作日

---

## 8. 验收标准

### 后端
- [ ] `get_index_trends()` 返回三大指数分时数据（241 点/天）
- [ ] `get_stock_ranking()` 返回上证/深证 A 股涨跌幅 Top 10
- [ ] `get_board_ranking()` 返回行业/概念/风格/地区板块排行
- [ ] `get_market_breadth()` 返回涨跌家数 + 总成交额
- [ ] `GET /api/market-overview` 返回完整 JSON，包含所有字段
- [ ] 后端并行请求，总延迟 < 5 秒
- [ ] 30 秒缓存命中，不重复请求

### 前端
- [ ] 三大指数分时图正确渲染（ECharts 折线 + 量能柱）
- [ ] 上证/深证 A 股涨跌幅 Top 10 列表正确显示
- [ ] 板块排行表支持行业/概念/风格/地区 Tab 切换
- [ ] 板块排行表支持表头排序
- [ ] 点击股票 → 右侧 MiniChart 显示分时图
- [ ] 24 小时滚动新闻正确显示
- [ ] 底部状态栏显示成交额 + 涨跌家数
- [ ] 数据自动刷新（指数 30 秒，新闻 60 秒）
- [ ] TopBar 新增「市场」按钮，点击跳转到 `/market`

### 通用
- [ ] 非交易时间显示最近交易日数据
- [ ] 请求失败时显示错误提示 + 重试按钮
- [ ] TypeScript 编译 0 错误

---

*文档基于 2026-09-03 通达信全景图截图 + akshare/push2 接口调研编写。*
