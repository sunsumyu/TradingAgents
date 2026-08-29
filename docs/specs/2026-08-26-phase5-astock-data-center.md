# Phase 5 规格：A 股特色数据中心（唤醒沉睡的后端深模块）

> 对标：东方财富数据中心 (data.eastmoney.com) / 同花顺数据中心 (data.10jqka.com.cn)
>
> 日期：2026-08-26 ｜ 状态：提案（依赖 Phase 4 工单 11-13 收尾）
>
> 前置文档：`2026-08-25-tradingview-quality-gui-master-plan.md` 第 6 节

---

## 1. 动机与杠杆分析

`tradingagents/dataflows/a_stock.py`（2600+ 行）里已实现一批东方财富数据中心级
功能，经过多 Agent 投研场景实战验证（含东财防封限流 `_em_get`、腾讯批量行情、
新浪/同花顺直连等适配层）。它们当前只服务于 Agent 分析管线，GUI 完全没有暴露。

**杠杆**：每个功能从「后端就绪」到「GUI 可见」只差三层薄适配：

```
沉睡深模块（已存在）                  新增薄层（本规格的工作量）
─────────────────────────            ──────────────────────────
get_dragon_tiger_board(ticker,      POST /api/astock-features  <- 单一端点
  trade_date, look_back_days)          │  请求 {feature, ticker, date, ...params}
get_chip_distribution(symbol,          │  响应 Pydantic 结构化模型
  curr_date, days)                     ▼
get_concept_blocks(ticker, ...)      GUI 面板组件（Tab 挂 MarketDataPanel 下方）
...（共 10 个函数）
```

工作量约为全新功能的 1/3：数据获取、防封限流、多源 fallback 全部已就绪。

**一个关键事实**：这批函数的返回值大多是 **markdown 文本**（为 LLM 设计），
不是结构化数据。GUI 暴露前需要文本解析层。这是本规格的主要新增工作量，
也是每个 feature 评估「解析难度」的原因。

---

## 2. 后端函数盘点（签名已核实，2026-08-26）

| # | 函数 | 签名（简化） | 返回 | 解析难度 | GUI 优先级 |
|---|------|------------|------|---------|-----------|
| 1 | `get_chip_distribution` | `(symbol, curr_date, days=90)` | md 文本（价格档位 % 分布） | 中（分段+数值行） | **P0 招牌** |
| 2 | `get_dragon_tiger_board` | `(ticker, trade_date, look_back_days=30)` | md 文本（上榜记录/席位） | 中（表格行） | **P0** |
| 3 | `get_northbound_flow` | `(curr_date, include_history=True)` | md 文本（当日+20日历史） | 低（数值行） | P1 |
| 4 | `get_concept_blocks` | `(ticker, ...)` | md 文本（分类板块列表） | 低（标题+列表） | P1 |
| 5 | `get_profit_forecast` | `(ticker, curr_date)` | md 文本（EPS 预测/前瞻估值） | 中 | P1 |
| 6 | `get_lockup_expiry` | `(ticker, trade_date, forward_days=90)` | md 文本（解禁批次） | 中（表格行） | P2 |
| 7 | `get_industry_comparison` | `(ticker, trade_date, top_n=20)` | md 文本（行业涨幅排名） | 低 | P2 |
| 8 | `get_hot_stocks` | `(curr_date="")` | md 文本（人气榜+题材） | 中 | P2 |
| 9 | `get_insider_transactions` | `(ticker)` | md 文本（股东/内部人动向） | 中 | P3 |
| 10 | `get_balance_sheet` / `get_cashflow` / `get_income_statement` | `(ticker, freq="quarterly", curr_date=None)` | md 文本（新浪财务三表） | 高（宽表） | P3 |

> 注：签名中的 `Annotated[...]` 是给 Agent 工具用的类型标注，直接调用传
> 字符串即可；`curr_date=None` 表示默认今天。

---

## 3. API 设计

### 3.1 单一端点（保持接口面小）

```
POST /api/astock-features
{
  "feature": "chip_distribution",     # 见 3.2 feature 名表
  "ticker": "000858",
  "date": "2026-08-26",
  "params": { "days": 90 }            # 可选，按 feature 透传
}
```

响应（统一信封）：

```json
{
  "feature": "chip_distribution",
  "ticker": "000858",
  "date": "2026-08-26",
  "data": { ... },                    # feature 专属结构（见 3.3）
  "raw_md": "..."                     # 原始 markdown（调试 + AI 上下文复用）
}
```

**设计理由（深模块视角）**：
- 调用者只需知道一个 URL + feature 名。新增 feature 不加端点。
- `raw_md` 保留原文：解析器不完美时前端可降级渲染 markdown；同时这同一端点
  未来可直连 AI 分析管线作为上下文输入（一处实现两处复用）。
- 解析器按 feature 名注册在一个 dispatch 表里（类似前端 SubIndicatorPanel
  的做法）：加 feature = 表里加一行 + 一个解析函数 + 一个 Pydantic 模型。

### 3.2 feature 名表

| feature 名 | 调用的后端函数 | 专属参数 |
|-----------|--------------|---------|
| `chip_distribution` | get_chip_distribution | `days: 90` |
| `dragon_tiger` | get_dragon_tiger_board | `look_back_days: 30` |
| `northbound_flow` | get_northbound_flow | `include_history: true` |
| `concept_blocks` | get_concept_blocks | - |
| `profit_forecast` | get_profit_forecast | - |
| `lockup_expiry` | get_lockup_expiry | `forward_days: 90` |
| `industry_comparison` | get_industry_comparison | `top_n: 20` |
| `hot_stocks` | get_hot_stocks | - |
| `insider_transactions` | get_insider_transactions | - |
| `balance_sheet` / `cashflow` / `income_statement` | 对应函数 | `freq: "quarterly"` |

非 A 股标的（非 6 位数字代码）：返回 400 + 明确错误（复用现有
`_is_astock` 判定，A 股层会主动拒绝非 A 股代码，见 `_reject_non_a_share`）。

### 3.3 data 结构（首批三个 P0/P1）

```python
# chip_distribution
class ChipDistributionData(BaseModel):
    price_levels: list[PriceLevelChip]   # 横向成本分布（主视图）
    profit_ratio: float | None           # 获利比例 %
    avg_cost: float | None               # 平均成本

class PriceLevelChip(BaseModel):
    price: float
    ratio: float        # 该价位筹码占比 %

# dragon_tiger
class DragonTigerData(BaseModel):
    appearances: list[DragonTigerAppearance]

class DragonTigerAppearance(BaseModel):
    date: str
    reason: str                    # 上榜原因
    net_buy_wan: float             # 净买入（万元）
    turnover_rate: float | None
    seats: list[DragonTigerSeat]   # 买卖席位明细

class DragonTigerSeat(BaseModel):
    name: str                      # 席位名称（机构/营业部）
    side: str                      # buy / sell
    amount_wan: float
    is_institution: bool

# northbound_flow
class NorthboundData(BaseModel):
    hgt_net_inflow: float | None      # 沪股通当日净流入（亿）
    sgt_net_inflow: float | None      # 深股通当日净流入（亿）
    history: list[NorthboundDay]      # 近 20 交易日

class NorthboundDay(BaseModel):
    date: str
    hgt: float
    sgt: float
```

---

## 4. GUI 设计

### 4.1 布局：MarketDataPanel 下方 Tab 区

```
MarketDataPanel
├── TradingViewLayout            # 主图区（不变）
├── FundamentalCards / NewsFeed  # 现有信息区（不变）
└── [新] AstockFeatureTabs       # 「资金 | 龙虎榜 | 筹码 | 板块 | 财务」
    ├── ChipPanel                # 横向成本分布图 + 获利比例 + 平均成本线
    ├── DragonTigerPanel         # 上榜记录表 + 席位明细（可展开行）
    ├── NorthboundPanel          # 沪深股通时间序列（复用 ECharts bar/line）
    ├── ConceptPanel             # 所属概念/板块标签云 + 点击过滤
    └── FinancialsPanel          # 三表 Tab（P3，宽表解析最难）
```

### 4.2 筹码分布面板（P0，同花顺招牌功能对标）

- 主视图：**横向**柱状图（Y 轴价格档、X 轴筹码占比），当前价水平线贯穿，
  当前价上方筹码以绿色（套牢盘）、下方红色（获利盘）着色。
- 顶部读数：获利比例 %、平均成本、90% 成本区间。
- 数据已由后端 20 档分箱（`num_bins = 20`），前端直接渲染无需再分箱。

### 4.3 龙虎榜面板（P0）

- 主表：日期 / 上榜原因 / 净买入(万) / 换手率，行可展开席位明细。
- 席位明细：买方列表（红）/卖方列表（绿），机构席位标记「机构」徽章。
- 空状态（近 30 日未上榜）复用后端文案。

### 4.4 交互约定

- Tab 懒加载：首次点击才请求该 feature（避免一次拉满 10 个数据源触发限流）。
- 请求竞态：复用 AbortController 模式（与周期切换一致）。
- 加载/错误态：骨架屏 + 可重试，错误显示 `raw_md` 降级渲染兜底。
- 东财系接口走后端 `_em_get` 全局限流，前端无需额外节流。

---

## 5. 实施顺序与工单拆分建议

| 工单 | 内容 | 依赖 |
|------|------|------|
| 5.01 | 端点骨架 + feature dispatch 表 + 信封模型 + 错误约定 | - |
| 5.02 | 筹码分布：解析器 + ChipDistributionData + ChipPanel | 5.01 |
| 5.03 | 龙虎榜：解析器 + DragonTigerData + DragonTigerPanel | 5.01 |
| 5.04 | 北向资金：解析器 + NorthboundPanel（时序图） | 5.01 |
| 5.05 | 概念板块 + 盈利预测（标签/卡片，轻量） | 5.01 |
| 5.06 | 解禁日历 + 行业对比 + 人气榜 | 5.01 |
| 5.07 | 财务三表 Tab（宽表解析，最难） | 5.01 |
| 5.08 | 价格预警（独立线：后台循环 + Tauri 通知，不依赖本表） | 工单10 已就绪 |

每个工单的验收都包含「真实 A 股标的实测」（如 000858/600519），与工单 10
的验证标准一致。

---

## 6. 风险与约束

| 风险 | 缓解 |
|------|------|
| markdown 解析脆弱（后端文案一改就崩） | 解析器集中在单文件便于批量修；`raw_md` 降级渲染兜底；为每个解析器写基于真实输出的快照测试 |
| 东财/同花顺接口风控 | 全部走既有 `_em_get` 限流 / 直连通道，不新增裸请求 |
| 财务三表宽表格式复杂 | 排 P3 最后做；先出 P0/P1 验证整条链路 |
| 非 A 股标的面板 | feature Tab 仅对 6 位数字代码显示（`_is_astock` 前端镜像判定） |
| 与 Agent 管线的耦合 | 本规格只读调用，不改 a_stock.py 内部；`raw_md` 反向供给 AI 是独立后续方向 |

---

## 7. 验收标准

- [x] `POST /api/astock-features` 对 10 个 feature 全部返回结构化 data + raw_md
- [x] 筹码分布面板：横向分布图渲染正确，获利比例/平均成本读数与后端一致
- [x] 龙虎榜面板：上榜记录 + 可展开席位明细，机构徽章正确
- [x] 北向资金：当日净流入 + 20 日历史时序图
- [x] 概念板块：标签药丸 + 分类分组表格，涨跌颜色正确
- [x] 盈利预测：现价/PE/Forward PE/PEG 读数 + EPS 柱状图(min-max 区间)
- [x] 解禁日历：历史批次表 + 未来90天待解禁警告
- [x] 人气榜：排行表 + 题材标签药丸
- [x] 价格预警：铃铛按钮 + AlertPanel + Tauri 桌面通知 + localStorage 持久化
- [x] 非 A 股标的：Tab 区隐藏或端点返回 400
- [x] 每个 feature 首次点击才加载，Tab 切换不重复请求
- [x] 解析器快照测试（真实输出样本）全部通过
