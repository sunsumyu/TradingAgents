# Phase 7 规格：交易员数据中心增强（对标通达信投资日历/新股/融资融券）

> 对标：通达信「数据」菜单 — 投资日历、新股中心、融资融券
>
> 日期：2026-09-03 ｜ 状态：提案
>
> 前置：Phase 5（A股特色数据中心）+ Phase 6（交易员级工具）
>
> 参考截图：通达信 TdxW 2026-09-03 5 张截图
>
> **[2026-09-27 指向]** 本规格已并入并裁决于
> [`2026-09-27-eastmoney-aligned-platform-plan.md`](2026-09-27-eastmoney-aligned-platform-plan.md)
> （Phase 10–12）。原文保留，作为功能细节来源。

---

## 1. 动机与差距分析

### 1.1 5 张截图功能对照

| 截图 | 功能 | 项目现状 | 差距 |
|------|------|----------|------|
| 图1 | K线行情（日线+MACD+VOL） | ✅ TradingViewChart + 25指标 | 无差距 |
| 图2 | **投资日历**（新股上市/发行/停复牌/特别处理/解禁） | ️ 后端有 `get_lockup_expiry`，前端有 `LockupPanel` | 缺综合日历视图：无新股日历、停复牌、特别处理 |
| 图3 | **新股中心**（新股发行预告/上市预告） | ❌ 未实现 | 全新功能 |
| 图4 | 龙虎榜个股+席位活跃度分析 | ✅ DragonTigerPanel 已实现 | 可增强：缺「席位活跃度分析」排行表 |
| 图5 | **融资融券**（排行/行业分布/市场统计） | ❌ 未实现 | 全新功能 |

### 1.2 akshare 数据接口可用性

以下 akshare 函数已验证可用（2026-09-03）：

| 功能 | akshare 函数 | 数据内容 |
|------|-------------|---------|
| 新股发行预告 | `stock_ipo_declare_em()` | 证券代码、名称、申购日期、发行量、市盈率等 |
| 新股上市预告 | `stock_new_ipo_cninfo()` | 上市日期、发行价、发行量等 |
| 融资融券明细 | `stock_margin_detail_sse()` / `stock_margin_detail_szse()` | 融资余额、融券余额、净买入等 |
| 融资融券汇总 | `stock_margin_sse()` / `stock_margin_szse()` | 市场总额统计 |
| 融资融券行业分布 | `stock_margin_ratio_pa()` | 行业融资余额占比 |
| 龙虎榜席位活跃度 | 已有 `get_dragon_tiger_board` | 可复用，增强席位排行 |

---

## 2. 后端函数设计

### 2.1 新股数据模块（新文件）

**文件**：`tradingagents/dataflows/a_stock/ipo_center.py`

```python
def get_ipo_declaration(curr_date: str = "") -> str:
    """新股发行预告。

    返回 markdown 表格：
    序号 | 证券代码 | 证券简称 | 申购日期 | 申购代码 | 申购价(元) |
    发行量(万) | 网上发行量(万) | 申购上限(万) | 市盈率(摊薄) | 中签号公布日
    """

def get_ipo_listing(curr_date: str = "") -> str:
    """新股上市预告。

    返回 markdown 表格：
    序号 | 证券代码 | 证券简称 | 上市日期 | 发行价(元) | 发行量(万) |
    网上发行量(万) | 市盈率(摊薄) | 申购日期 | 中签率%
    """
```

### 2.2 融资融券模块（新文件）

**文件**：`tradingagents/dataflows/a_stock/margin_trading.py`

```python
def get_margin_detail(market: str = "sh", curr_date: str = "") -> str:
    """融资融券个股明细排行。

    返回 markdown 表格：
    序号 | 证券代码 | 证券简称 | 融资余额(亿) | 占流通市值% |
    买入额 | 偿还额 | 净买入 | 融券余量 | 卖出量 | 偿还量 | 净卖出 | 融资融券差值
    """

def get_margin_market_stat(market: str = "total", curr_date: str = "") -> str:
    """融资融券市场统计（时间序列）。

    返回 markdown 表格：日期 | 融资余额(亿) | 融券余额(亿) | 融资融券差值(亿)
    """

def get_margin_industry_distribution(curr_date: str = "") -> str:
    """融资融券行业分布。

    返回 markdown 表格：行业 | 融资余额占比% | 融券余额占比%
    """
```

### 2.3 投资日历聚合（扩展现有模块）

**文件**：扩展现有 `eastmoney.py` 或新增 `investment_calendar.py`

```python
def get_investment_calendar(curr_date: str = "") -> str:
    """投资日历 — 聚合当日所有市场事件。

    子事件：
    - 首发新股上市
    - 首发新股发行
    - 沪深停复牌
    - 特别处理（ST/摘帽）
    - 限售解禁

    返回 markdown 分组：
    # 投资日历 | {date}

    ## 首发新股上市（共 N 条记录）
    | 代码 | 简称 | 说明 |

    ## 首发新股发行（共 N 条记录）
    | 代码 | 简称 | 说明 |

    ## 沪深停复牌（共 N 条记录）
    | 代码 | 简称 | 停牌时间 | 复牌时间 | 说明 | 原因 |

    ## 特别处理（共 N 条记录）
    | 代码 | 简称 | 说明 |

    ## 限售解禁（共 N 条记录）
    | 代码 | 简称 | 解禁日期 | 解禁数量(万) | 占总股本% | 解禁原因 |
    """
```

### 2.4 龙虎榜席位活跃度（增强现有模块）

**文件**：扩展 `eastmoney.py` 中 `get_dragon_tiger_board`

```python
def get_seat_activity_analysis(curr_date: str = "", period: str = "1个月") -> str:
    """席位活跃度分析。

    返回 markdown 表格：
    序号 | 营业部名称 | 龙虎榜成交额(万) | 上榜次数 | 买入次数 |
    买入额(万) | 卖出次数 | 卖出额(万) | 净买入额(万)
    """

def get_stock_activity_analysis(curr_date: str = "", period: str = "1个月") -> str:
    """股票活跃度分析。

    返回 markdown 表格：
    序号 | 证券代码 | 证券简称 | 最近上榜日 | 龙虎榜成交额(万) |
    上榜次数 | 买入额(万) | 卖出额(万) | 净买入额(万)
    """
```

---

## 3. API 设计

### 3.1 扩展现有 FEATURE_TABLE

在 `astock_features.py` 的 `_build_feature_table()` 中新增 7 个 feature：

| feature 名 | 调用的后端函数 | 专属参数 | 解析难度 |
|-----------|--------------|---------|---------|
| `ipo_declaration` | `get_ipo_declaration` | - | 低（表格行） |
| `ipo_listing` | `get_ipo_listing` | - | 低（表格行） |
| `margin_detail` | `get_margin_detail` | `market: "sh"\|"sz"` | 中（数值行） |
| `margin_market_stat` | `get_margin_market_stat` | `market: "total"\|"sh"\|"sz"` | 中（时序） |
| `margin_industry` | `get_margin_industry_distribution` | - | 低（表格行） |
| `investment_calendar` | `get_investment_calendar` | - | 中（多分组） |
| `seat_activity` | `get_seat_activity_analysis` | `period: "1个月"` | 中（表格行） |
| `stock_activity` | `get_stock_activity_analysis` | `period: "1个月"` | 中（表格行） |

### 3.2 新增端点（可选，保持单一端点原则）

继续使用 `POST /api/astock-features`，无需新增端点。

请求示例：
```json
{
  "feature": "ipo_declaration",
  "ticker": "000000",
  "date": "2026-09-03",
  "params": {}
}
```

---

## 4. GUI 设计

### 4.1 新股中心面板

**新组件**：`tradingagents_gui/src/components/astock/IpoCenterPanel.tsx`

布局对标截图 3：
```
┌─────────────────────────────────────────────────────┐
│  新股发行预告                              [日期选择] │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 序号 | 代码 | 简称 | 申购日 | 申购价 | 发行量 |…  │ │
│ │  1  |688837| 信诺维 |09-03  | 27.60 |6532万 |…  │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│  新股上市预告                                        │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 序号 | 代码 | 简称 | 上市日 | 发行价 | 发行量 |…  │ │
│ │  1  |920071| 金钛股份|09-03  |  9.72 |4500万 |…  │ │
│ ─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

- 两个子表：发行预告 + 上市预告
- 日期选择器（默认今日），可翻页查看历史/未来
- 点击代码可跳转到该股 K 线图
- 今日日期高亮标记

### 4.2 融资融券面板

**新组件**：`tradingagents_gui/src/components/astock/MarginTradingPanel.tsx`

布局对标截图 5：
```
┌─────────────────────────────────────────────────────┐
│  [沪市] [深市] [京市]                        [日期] 更多>>│
│ ┌─────────────────────────────────────────────────┐ │
│ │ 序号 | 代码 | 简称 | 融资余额 | 占流通% | 净买入 |…│ │
│ │  1  |601919|中远海控| 35.89亿 |  1.74  | 2.08亿 |…│ │
│ ─────────────────────────────────────────────────┘ │
│                                                     │
│  融资融券行业分布          [融资余额占比][融券余额占比]  │
│ ┌─────────────────────────────────────────────────┐ │
│ │         ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇            │ │
│ │  综合  煤炭  社会  钢铁  …  计算机  电子            │ │
│ └───────────────────────────────────────────────── │
│                                                     │
│  融资融券市场统计          [合计][沪市][深市][京市]    │
│                  [融资余额][融券余额][融资融券差值]    │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 32000 ┤        ╱╲                                │ │
│ │ 30000 ┤      ╱    ╲    ╱╲                        │ │
│ │ 28000 ┤    ╱        ╲╱    ╲                      │ │
│ │       └──────────────────────                    │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

- 三个子区域：个股排行表 + 行业分布柱状图 + 市场统计折线图
- 市场切换 Tab：沪市/深市/京市
- 行业分布：ECharts 柱状图，按融资余额占比排序
- 市场统计：ECharts 折线图/面积图，支持融资余额/融券余额/差值切换

### 4.3 投资日历面板

**新组件**：`tradingagents_gui/src/components/astock/InvestmentCalendarPanel.tsx`

布局对标截图 2：
```
┌─────────────────────────────────────────────────────┐
│  [每日特别提示][分红融资][股东大会][财报披露][涨跌停分析] │
│                                                     │
│  ┌─── 日历 ───┐   首发新股上市（共 1 条记录）           │
│  │ 2026年 9月  │   ┌───────────────────────────────┐ │
│  │ 日 一 二 …  │   │ 920071 | 金钛股份 | 首发新股上市日│ │
│  │        3 ◉  │   └───────────────────────────────┘ │
│  │ 今天 [确定] │   首发新股发行（共 3 条记录）           │
│  └────────────┘   ┌───────────────────────────────┐ │
│                   │ 688801 | 燧原科技 | 中签率公告日  │ │
│                   │ 688837 | 信诺维 | 首发新股网上…  │ │
│                   └─────────────────────────────── │
│                                                     │
│   沪深停复牌（共 1 条记录）                            │
│   ┌───────────────────────────────────────────────┐ │
│   │ 300472 | ST新元 | 09-02 09:30 | 09-03 09:30   │ │
│   ─────────────────────────────────────────────── │
│                                                     │
│   限售解禁（共 7 条记录）                              │
│   ┌───────────────────────────────────────────────┐ │
│   │ 002915 | 中欣氟材 | 09-03 | 980.50万 | 2.92%  │ │
│   └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

- 左侧日历导航（月度日历，可前后翻月）
- 顶部子 Tab：每日特别提示 / 分红融资 / 股东大会 / 财报披露 / 涨跌停分析
- 分组显示：首发新股上市、首发新股发行、停复牌、特别处理、限售解禁
- 每组带记录计数，点击可展开详情
- 日期高亮：有事件的日期标记圆点

### 4.4 龙虎榜增强：席位/股票活跃度面板

**扩展现有** `DragonTigerPanel.tsx` 或新建 `SeatActivityPanel.tsx`

```
┌─────────────────────────────────────────────────────┐
│  席位活跃度分析           [一个月][三个月][六个月][一年]  │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 序号 | 营业部名称 | 成交额(万) | 上榜次数 | 净买入 │ │
│ │  1  | 机构专用   | 1931万   |  3734   | -691万  │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│  股票活跃度分析           [一个月][三个月][六个月][一年]  │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 序号 | 代码 | 简称 | 最近上榜日 | 成交额 | 上榜次数│ │
│ │  1  |301520| 万邦医药| 09-02   |2035万  |  27    │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 5. 数据源适配

### 5.1 新股数据

```python
# 复用 akshare
import akshare as ak

def _fetch_ipo_declaration():
    df = ak.stock_ipo_declare_em()
    # 列：序号, 股票代码, 股票简称, 申购日期, 申购代码, 申购价, 发行量, ...

def _fetch_ipo_listing():
    df = ak.stock_new_ipo_cninfo()
    # 列：证券代码, 证券简称, 上市日期, 发行价, 发行量, ...
```

### 5.2 融资融券数据

```python
def _fetch_margin_detail(market: str):
    if market == "sh":
        df = ak.stock_margin_detail_sse(date=curr_date)
    elif market == "sz":
        df = ak.stock_margin_detail_szse(date=curr_date)

def _fetch_margin_market_stat(market: str):
    if market == "sh":
        df = ak.stock_margin_sse(start_date=..., end_date=...)
    elif market == "sz":
        df = ak.stock_margin_szse(start_date=..., end_date=...)

def _fetch_margin_industry():
    df = ak.stock_margin_ratio_pa()
```

### 5.3 投资日历数据

```python
# 投资日历需要聚合多个数据源：
# 1. 新股日历 → akshare stock_ipo_declare_em / stock_new_ipo_cninfo
# 2. 停复牌 → 东财 datacenter API
# 3. 特别处理 → 东财 datacenter API
# 4. 解禁 → 已有 get_lockup_expiry
```

### 5.4 龙虎榜席位活跃度

```python
# 复用现有 _eastmoney_datacenter，调用不同报表编号
# 席位活跃度：reportId=RPT_DAILYBILLBOARD_DETAILSNEW
# 股票活跃度：reportId=RPT_DMSK_TS_STOCKNEW
```

---

## 6. 实施顺序与工单拆分

| 工单 | 内容 | 依赖 | 预估 |
|------|------|------|------|
| 7.01 | 新股数据模块 `ipo_center.py` + 解析器 + FEATURE_TABLE 注册 | - | 0.5d |
| 7.02 | 融资融券模块 `margin_trading.py` + 解析器 + FEATURE_TABLE 注册 | - | 1d |
| 7.03 | 投资日历模块 `investment_calendar.py` + 聚合逻辑 | 7.01, 已有 lockup | 1d |
| 7.04 | 龙虎榜席位/股票活跃度增强 | 已有 dragon_tiger | 0.5d |
| 7.05 | GUI：IpoCenterPanel（新股中心面板） | 7.01 | 0.5d |
| 7.06 | GUI：MarginTradingPanel（融资融券面板） | 7.02 | 1d |
| 7.07 | GUI：InvestmentCalendarPanel（投资日历面板） | 7.03 | 1d |
| 7.08 | GUI：DragonTigerPanel 增强（席位/股票活跃度子 Tab） | 7.04 | 0.5d |
| 7.09 | AstockFeatureTabs 注册新面板 + 路由 | 7.05-7.08 | 0.5d |
| 7.10 | 快照测试 + 集成测试 | 全部 | 0.5d |

**总计**：约 6 个工作日

---

## 7. 解析器设计

### 7.1 IPO 解析器

```python
def _parse_ipo_declaration(raw_md: str) -> dict[str, Any]:
    """解析新股发行预告 markdown 表格。"""
    # 输出：{ "items": [ { "code", "name", "subscribe_date", "subscribe_code",
    #   "price", "volume_wan", "online_volume_wan", "subscribe_limit_wan",
    #   "pe_ratio", "lottery_date" } ], "total": N }

def _parse_ipo_listing(raw_md: str) -> dict[str, Any]:
    """解析新股上市预告 markdown 表格。"""
```

### 7.2 融资融券解析器

```python
def _parse_margin_detail(raw_md: str) -> dict[str, Any]:
    """解析融资融券个股明细。"""
    # 输出：{ "items": [...], "market": "sh", "date": "..." }

def _parse_margin_market_stat(raw_md: str) -> dict[str, Any]:
    """解析融资融券市场统计时序。"""
    # 输出：{ "items": [ { "date", "margin_balance_yi", "short_balance_yi", "diff_yi" } ] }

def _parse_margin_industry(raw_md: str) -> dict[str, Any]:
    """解析融资融券行业分布。"""
    # 输出：{ "items": [ { "industry", "margin_ratio_pct", "short_ratio_pct" } ] }
```

### 7.3 投资日历解析器

```python
def _parse_investment_calendar(raw_md: str) -> dict[str, Any]:
    """解析投资日历多分组 markdown。"""
    # 输出：{
    #   "date": "2026-09-03",
    #   "ipo_listing": [ ... ],
    #   "ipo_declaration": [ ... ],
    #   "suspension_resumption": [ ... ],
    #   "special_treatment": [ ... ],
    #   "lockup_expiry": [ ... ]
    # }
```

### 7.4 龙虎榜活跃度解析器

```python
def _parse_seat_activity(raw_md: str) -> dict[str, Any]:
    """解析席位活跃度排行。"""
    # 输出：{ "period": "1个月", "items": [ { "name", "turnover_wan",
    #   "appear_count", "buy_count", "buy_amount_wan",
    #   "sell_count", "sell_amount_wan", "net_buy_wan" } ] }

def _parse_stock_activity(raw_md: str) -> dict[str, Any]:
    """解析股票活跃度排行。"""
```

---

## 8. 风险与约束

| 风险 | 缓解 |
|------|------|
| akshare 接口变更 | 封装在独立模块，便于适配层修改；快照测试监控输出格式 |
| 投资日历聚合复杂（多数据源） | 按子事件独立获取，聚合层只做 markdown 拼接，不做强关联 |
| 融资融券数据量大（全市场） | 只取 Top 50 排行 + 汇总统计，不全量拉取 |
| 东财接口限流 | 复用 `_em_get` 限流机制，日历聚合串行请求 |
| 非 A 股标的 | 新股/融资融券面板仅对 A 股市场显示 |

---

## 9. 验收标准

### 新股中心
- [ ] `get_ipo_declaration()` 返回当日新股发行预告 markdown
- [ ] `get_ipo_listing()` 返回当日新股上市预告 markdown
- [ ] IpoCenterPanel 双表渲染，今日日期高亮
- [ ] 点击股票代码跳转 K 线图

### 融资融券
- [ ] `get_margin_detail()` 沪/深两市 Top 50 排行
- [ ] `get_margin_market_stat()` 市场统计时序数据
- [ ] `get_margin_industry_distribution()` 行业分布数据
- [ ] MarginTradingPanel 三区域渲染：排行表 + 行业柱状图 + 市场折线图
- [ ] 市场切换（沪/深/京）+ 统计维度切换（融资/融券/差值）

### 投资日历
- [ ] `get_investment_calendar()` 聚合 5 类事件
- [ ] InvestmentCalendarPanel 日历导航 + 分组展示
- [ ] 日期切换功能正常

### 龙虎榜增强
- [ ] `get_seat_activity_analysis()` 席位活跃度排行
- [ ] `get_stock_activity_analysis()` 股票活跃度排行
- [ ] DragonTigerPanel 新增「席位活跃度」「股票活跃度」子 Tab
- [ ] 周期切换（1月/3月/6月/1年）

### 通用
- [ ] 每个 feature 在 FEATURE_TABLE 中注册
- [ ] 每个解析器有快照测试（真实输出样本）
- [ ] 非 A 股标的返回 400 或面板隐藏
- [ ] 懒加载：首次点击才请求

---

*文档基于 2026-09-03 通达信截图 + akshare 接口调研编写。*
