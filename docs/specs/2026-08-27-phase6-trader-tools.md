# Phase 6: 交易员级工具 — 工单列表

> 日期：2026-08-27
> 前置：Phase 5 全部完成

## 概览

Phase 6 聚焦三大功能：**自然语言选股器**（核心，独有优势）、**多图表布局**、**模拟组合**。
价格预警已在 5.08 完成；K线回放和 L2 盘口推迟到 Phase 7（成本高、ROI 低）。

---

## 工单 6.01 — 自然语言选股器（后端）

**目标**：用户输入自然语言（如「帮我找北向连续加仓且PE<20的消费股」），LLM 翻译为结构化查询，后端执行并返回候选列表。

### 后端设计

**新端点**：`POST /api/screener`

请求体：
```json
{
  "query": "北向连续加仓且PE<20的消费股",
  "market": "astock",
  "max_results": 20
}
```

响应体：
```json
{
  "query": "北向连续加仓且PE<20的消费股",
  "parsed_criteria": {
    "filters": [
      {"field": "northbound_flow", "condition": "连续加仓", "period": "5日"},
      {"field": "pe_ratio", "operator": "<", "value": 20},
      {"field": "industry", "operator": "in", "value": ["消费", "食品饮料"]}
    ]
  },
  "results": [
    {"ticker": "600519", "name": "贵州茅台", "price": 1500.0, "change_pct": 2.1, "pe": 18.5, "northbound_5d": "+12.3亿", "score": 92},
    ...
  ],
  "count": 15,
  "suggestion": "这些股票满足北向加仓+低估值条件，建议关注消费龙头"
}
```

**实现要点**：
1. 新文件 `tradingagents_api/screener.py`：
   - `ScreenerFilter` / `ScreenerResult` / `ScreenerResponse` Pydantic 模型
   - `_build_screener_prompt(query)` — 构造 LLM prompt，让 LLM 将自然语言翻译为 JSON filter 列表
   - `_execute_filters(filters, market)` — 对每个 filter 调用对应的 astock_features 函数
   - `_score_and_rank(results, filters)` — 综合打分排序
   - `run_screener(query, market, max_results)` — 主入口

2. 可用 filter 字段（对应 Phase 5 已有数据）：
   | Filter 字段 | 数据来源 | 说明 |
   |-------------|---------|------|
   | `northbound_flow` | `get_northbound_flow` | 北向资金流入 |
   | `hot_stocks` | `get_hot_stocks` | 人气排名 |
   | `concept_blocks` | `get_concept_blocks` | 概念板块 |
   | `chip_distribution` | `get_chip_distribution` | 筹码集中度 |
   | `dragon_tiger` | `get_dragon_tiger_board` | 龙虎榜席位 |
   | `industry_comparison` | `get_industry_comparison` | 行业资金排名 |
   | `profit_forecast` | `get_profit_forecast` | 盈利预测 |
   | `lockup_expiry` | `get_lockup_expiry` | 解禁风险 |

3. LLM prompt 约束：输出严格 JSON，使用 `response_format={"type": "json_object"}`（支持的 provider）或在 prompt 中要求 JSON 输出。

4. 后端使用 `create_quick_llm(config)` — 选股查询不需要深度推理。

### 验收标准
- [ ] `POST /api/screener` 端点可用
- [ ] 自然语言查询能正确翻译为 filter JSON
- [ ] 结果列表包含 ticker、名称、价格、涨跌幅、相关指标
- [ ] 空结果返回空列表 + 提示信息
- [ ] 后端超时 30s，失败返回错误信息

---

## 工单 6.02 — 自然语言选股器（前端）

**目标**：选股器 UI，输入框 + 结果表格 + 一键加入自选。

### 前端设计

**新组件**：`tradingagents_gui/src/components/screener/ScreenerPanel.tsx`

布局：
```
┌─────────────────────────────────────────────┐
│ 🔍 自然语言选股                              │
│ ┌─────────────────────────────────┐ [搜索]  │
│ │ 输入选股条件...                   │         │
│ └─────────────────────────────────┘         │
│ ┌─────────────────────────────────────────┐ │
│ │ 热门：北向加仓 | 低PE | 高人气 | 龙虎榜  │ │
│ └─────────────────────────────────────────┘ │
│ ──────────────── 结果 (15只) ────────────── │
│ □ 代码   名称    现价   涨跌%  PE   北向5日  │
│ ☑ 600519 贵州茅台 1500  +2.1%  18.5 +12.3亿 │
│ □ 000858 五粮液   168   +1.8%  15.2 +8.7亿  │
│ ...                                         │
│ [全选] [加入自选] [导出CSV]                   │
└─────────────────────────────────────────────┘
```

**实现要点**：
1. `ScreenerPanel.tsx` — 主组件，包含搜索框、热门标签、结果表格
2. `ScreenerTable.tsx` — 可排序表格组件，列可点击排序
3. `useScreener.ts` — hook，管理查询状态、loading、结果缓存
4. 热门标签预填查询词：`["北向加仓", "低PE消费股", "高人气龙头", "龙虎榜净买入", "概念龙头"]`
5. 行选择 checkbox，支持全选 + 批量加入自选
6. "加入自选" 按钮调用 `watchlist-store.ts` 的 `addItem`

### 路由集成
- 新增 Tab：在 TopBar 或 MarketDataPanel 中加入「选股」入口
- 或作为 TradingViewLayout 侧栏的新面板

### 验收标准
- [ ] 输入框可输入自然语言查询
- [ ] 热门标签点击自动填充并搜索
- [ ] 结果表格显示所有 filter 指标列
- [ ] 列头可点击排序
- [ ] 勾选后可批量加入自选
- [ ] Loading 状态 + 空结果提示
- [ ] 错误状态显示

---

## 工单 6.03 — 多图表布局

**目标**：支持 1×1 / 1×2 / 2×2 三种布局，每个窗格独立 ticker + 周期，光标同步。

### 后端
无新端点。现有 `/api/chart-data` 已支持多 ticker 并发调用。

### 前端设计

**新组件**：
- `tradingagents_gui/src/components/tradingview/MultiChartLayout.tsx` — 布局容器
- `tradingagents_gui/src/components/tradingview/ChartPane.tsx` — 单窗格（复用 TradingViewChart）

布局选择器在 ChartHeader 旁：
```
[1×1] [1×2] [2×2]
```

**实现要点**：
1. `MultiChartLayout.tsx`：
   - 状态：`layout: "1x1" | "1x2" | "2x2"`, `panes: ChartPaneConfig[]`
   - 每个 pane 独立：`{ ticker, timeframe, indicators }`
   - CSS Grid 布局：`grid-template-columns` 根据 layout 变化
   - 光标同步：共享 crosshair state（时间轴对齐）

2. `ChartPane.tsx`：
   - 包装 `TradingViewChart` + `IndicatorBar` + `SubIndicatorMinis`
   - 每个 pane 独立数据加载（AbortController 竞态取消）
   - ticker 切换：pane 内搜索框或拖拽自选股

3. 光标同步：
   - 全局 `CrosshairContext`（React Context）
   - 一个 pane 的 crosshair 变化 → 其他 pane 同步到相同时间点
   - 使用 ECharts `connect` API 或自定义 dispatch

### 验收标准
- [ ] 三种布局切换流畅
- [ ] 每个窗格独立加载数据
- [ ] 光标时间轴同步
- [ ] 布局偏好持久化到 localStorage
- [ ] 单窗格可全屏（双击标题栏）

---

## 工单 6.04 — 模拟组合

**目标**：基于 AI 信号的模拟交易组合，记录买卖操作，追踪收益率。

### 后端

**新端点**：
- `GET /api/portfolio` — 获取当前组合
- `POST /api/portfolio/trade` — 执行模拟交易
- `GET /api/portfolio/history` — 交易历史
- `GET /api/portfolio/performance` — 收益率曲线

**数据存储**：JSON 文件 `~/.tradingagents/portfolio.json`

请求/响应：
```json
// POST /api/portfolio/trade
{
  "ticker": "600519",
  "action": "buy",       // buy | sell
  "quantity": 100,
  "price": 1500.0,       // 可选，默认用实时价
  "reason": "AI信号: 强烈买入"  // 可选
}

// GET /api/portfolio
{
  "positions": [
    {"ticker": "600519", "name": "贵州茅台", "quantity": 100, "avg_cost": 1480.0, "current_price": 1500.0, "pnl": 2000.0, "pnl_pct": 1.35}
  ],
  "cash": 980000.0,
  "total_value": 1130000.0,
  "total_pnl": 13000.0,
  "total_pnl_pct": 1.16
}
```

### 前端设计

**新组件**：`tradingagents_gui/src/components/portfolio/PortfolioPanel.tsx`

布局：
```
┌──────────────────────────────────────────┐
│ 💼 模拟组合          总资产 ¥1,130,000    │
│ ──────────────────────────────────────── │
│ 持仓                                    │
│ 代码   名称    数量  成本    现价   盈亏   │
│ 600519 贵州茅台 100  1480   1500  +2.0%  │
│ 000858 五粮液   200  165    168   +1.8%  │
│ ──────────────────────────────────────── │
│ 现金: ¥980,000                          │
│ ──────────────────────────────────────── │
│ [交易记录] [收益曲线]                     │
└──────────────────────────────────────────┘
```

**实现要点**：
1. `PortfolioPanel.tsx` — 主组件：持仓表 + 操作按钮
2. `TradeDialog.tsx` — 交易弹窗：买入/卖出 + 数量 + 价格
3. `PerformanceChart.tsx` — 收益率曲线（ECharts 折线图）
4. `TradeHistory.tsx` — 交易记录表格
5. `usePortfolio.ts` — hook，管理组合状态 + API 调用

### AI 联动
- 分析报告完成后，自动提示「基于 AI 信号创建交易？」
- `PortfolioManager` 的 Buy/Sell 决策可一键执行为模拟交易
- 交易原因自动关联 AI 分析结论

### 验收标准
- [ ] 买入/卖出操作正确更新持仓
- [ ] 盈亏实时计算（基于 realtime prices）
- [ ] 交易记录持久化
- [ ] 收益率曲线展示
- [ ] AI 报告可一键触发交易
- [ ] 现金余额正确扣减/增加

---

## 工单 6.05 — Phase 6 集成测试 + 构建

**目标**：确保所有 Phase 6 功能端到端可用。

### 任务
1. 后端 pytest：screener prompt 构建、filter 执行、portfolio CRUD
2. 前端 vitest：ScreenerPanel 渲染、PortfolioPanel 计算、MultiChartLayout 切换
3. Tauri 构建验证
4. 端到端手动测试清单

### 验收标准
- [ ] 所有新测试通过
- [ ] Tauri `cargo tauri build` 成功
- [ ] 手动测试清单全部通过
