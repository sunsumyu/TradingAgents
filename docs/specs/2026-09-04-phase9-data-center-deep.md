# Phase 9 规格：数据中心深度页面（对标通达信「数据」菜单）

> 对标：通达信「数据」菜单 — 增持减持/大宗交易/增发送配/财报数据/价值分析/机构持股
>
> 日期：2026-09-04 ｜ 状态：提案
>
> 前置：Phase 5（A股特色数据中心）+ Phase 7（交易员数据中心）+ Phase 8（市场全景图 + PG 缓存）
>
> **[2026-09-27 指向]** 本规格已并入并裁决于
> [`2026-09-27-eastmoney-aligned-platform-plan.md`](2026-09-27-eastmoney-aligned-platform-plan.md)
> （Phase 10–12）。注意：§3.1 的 5 个模块已实现，但 §4.2 的 FEATURE_TABLE 注册与
> §5 的面板可达性未完成 —— 见新方案 §2.3 与新工单 06/07。原文保留。

---

## 1. 截图功能分析

### 6 张截图对照

| 截图 | 通达信功能 | 核心元素 | 项目现状 |
|------|-----------|---------|---------|
| 图1 | **增持减持** | 月度增减持柱状图 + 重要股东持股变动明细表 | ️ `insider_transactions` 有股东动向但无图表、无筛选 |
| 图2 | **大宗交易** | 个股明细表 + 行业分布柱状图 + 大盘统计柱状图 |  未实现 |
| 图3 | **增发送配** | 分红送转明细表（送股/转股/派息/收益/预案公告日/除权日） |  未实现 |
| 图4 | **财报数据** | 业绩预告表（预告类型 + 预告内容 + 预告日期） | ⚠️ `profit_forecast` 有盈利预测但缺业绩预告/快报 |
| 图5 | **价值分析** | 分析师评级表（评级/目标价/EPS预测/研究机构） | ⚠️ `profit_forecast` 部分覆盖但缺评级/目标价 |
| 图6 | **机构持股** | 机构持仓明细表（持股机构数/市值/占流通股比/仓位类型） |  未实现 |

### 共同特征
- 所有页面都有**市场筛选 Tab**：全部股票/沪市主板/科创板/深市主板/创业板/北交所
- 大部分页面有**日期选择器**
- 大部分页面有**搜索框**（输入代码、拼音和简称）
- 数据均为**表格 + 可选图表**组合

---

## 2. 数据源映射（akshare 验证通过）

| 功能 | akshare 函数 | 数据内容 | 状态 |
|------|-------------|---------|------|
| 增减持 | `stock_share_hold_change_sse/szse/bse()` | 股东持股变动明细 | ✅ 可用 |
| 增减持图表 | `stock_gdfx_holding_change_em()` | 大股东增减持趋势 | ✅ 可用 |
| 大宗交易明细 | `stock_dzjy_mrmx()` | 每日大宗交易明细 | ✅ 可用 |
| 大宗交易行业 | `stock_dzjy_hygtj()` | 行业溢价/折价统计 | ✅ 可用 |
| 大宗交易统计 | `stock_dzjy_sctj()` | 大盘大宗交易统计 | ✅ 可用 |
| 增发送配 | `stock_fhps_em()` | 分红送转方案 | ✅ 可用 |
| 业绩预告 | `stock_yjbb_em()` | 业绩报表 | ✅ 可用 |
| 业绩快报 | `stock_yjkb_em()` | 业绩快报 | ✅ 可用 |
| 机构持股 | `stock_jgdy_detail_em()` | 机构持股明细 | ✅ 可用 |
| 机构持股统计 | `stock_jgdy_tj_em()` | 机构持股统计 | ✅ 可用 |
| 基金持股 | `stock_report_fund_hold()` | 基金持仓明细 | ✅ 可用 |

---

## 3. 后端模块设计

### 3.1 新文件

```
tradingagents/dataflows/a_stock/
├── block_trade.py          # 大宗交易
├── dividend_bonus.py       # 增发送配（分红送转）
├── earnings_forecast.py    # 业绩预告/快报
├── analyst_rating.py       # 分析师评级/目标价/EPS预测
└── institutional_hold.py   # 机构持股
```

### 3.2 扩展现有文件

```
tradingagents/dataflows/a_stock/insider_transactions.py
  → 新增：get_insider_change_chart() 返回柱状图数据
```

### 3.3 函数签名

```python
# 增减持增强
def get_insider_change_chart(ticker: str = "", market: str = "all", curr_date: str = "") -> str:
    """增减持柱状图数据（按月份聚合增持/减持金额）"""

# 大宗交易
def get_block_trade_detail(curr_date: str = "", market: str = "all") -> str:
    """个股大宗交易明细"""
def get_block_trade_industry(month: str = "") -> str:
    """大宗交易行业分布（溢价/折价率 + 成交金额 + 成交次数）"""
def get_block_trade_market_stat(month: str = "") -> str:
    """大盘大宗交易统计"""

# 增发送配
def get_dividend_bonus(curr_date: str = "", market: str = "all", status: str = "all") -> str:
    """分红送转方案明细（送股/转股/派息/预案公告日/除权日/方案进度）"""

# 业绩预告/快报
def get_earnings_forecast(curr_date: str = "", forecast_type: str = "all") -> str:
    """业绩预告（预告类型 + 预告内容 + 预告日期）"""
def get_earnings_express(curr_date: str = "") -> str:
    """业绩快报"""

# 分析师评级
def get_analyst_rating(curr_date: str = "", period: str = "一月内") -> str:
    """个股投资评级（评级/目标价/EPS预测/研究机构/标题）"""

# 机构持股
def get_institutional_hold(report_date: str = "", inst_type: str = "all", position_type: str = "all") -> str:
    """机构持股明细（持股机构数/持仓数量/市值/占流通股比/仓位类型）"""
```

---

## 4. API 设计

### 4.1 扩展现有端点

继续使用 `POST /api/astock-features`，新增 7 个 feature key：

| feature 名 | 调用函数 | 专属参数 |
|-----------|---------|---------|
| `insider_change_chart` | `get_insider_change_chart` | `market: "all"\|"sh"\|"sz"` |
| `block_trade_detail` | `get_block_trade_detail` | `market: "all"\|"sh"\|"sz"` |
| `block_trade_industry` | `get_block_trade_industry` | `month: "2026-09"` |
| `block_trade_market_stat` | `get_block_trade_market_stat` | `month: "2026-09"` |
| `dividend_bonus` | `get_dividend_bonus` | `market, status: "all"\|"plan"\|"implemented"` |
| `earnings_forecast` | `get_earnings_forecast` | `forecast_type: "all"\|"rise"\|"fall"\|...` |
| `analyst_rating` | `get_analyst_rating` | `period: "一月内"` |
| `institutional_hold` | `get_institutional_hold` | `report_date, inst_type, position_type` |

### 4.2 FEATURE_TABLE 注册

每个 feature 在 `_build_feature_table()` 中注册，复用 `_passthrough_parser`（markdown 表格输出）。

---

## 5. GUI 设计

### 5.1 新增面板组件

```
tradingagents_gui/src/components/astock/
├── BlockTradePanel.tsx         # 大宗交易（明细表 + 行业分布图 + 大盘统计图）
├── DividendBonusPanel.tsx      # 增发送配（分红送转表）
├── EarningsForecastPanel.tsx   # 财报数据（业绩预告/快报 Tab）
├── AnalystRatingPanel.tsx      # 价值分析（分析师评级表）
└── InstitutionalHoldPanel.tsx  # 机构持股（机构持仓表 + 仓位类型 Tab）
```

### 5.2 扩展现有面板

```
InsiderTransactionsPanel.tsx
  → 新增「增减持趋势图」子区域（ECharts 柱状图）
```

### 5.3 通用 UI 模式

所有面板共享：
- **市场筛选 Tab**：全部股票/沪市主板/科创板/深市主板/创业板/北交所
- **日期选择器**：默认当月/当日
- **搜索框**：输入代码、拼音和简称（前端过滤）
- **分页**：每页 50 条

### 5.4 大宗交易面板布局

```
┌────────────────────────────────────────────────────────┐
│  个股大宗交易                              [日期] 更多>>│
│ ┌────────────────────────────────────────────────────┐ │
│ │ 序号 | 代码 | 简称 | 成交价 | 收盘价 | 溢折价% |…   │ │
│ │ 营业部：买入:xxx 卖出:xxx（红色/绿色标注）           │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│  大宗交易行业分布  统计月度:2026-09                      │
│  [溢折价率] [成交金额] [成交次数]                        │
│ ────────────────────────────────────────────────────┐ │
│ │  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇                        │ │
│ │  半导体 互联网 汽车 医药 建筑 ...                    │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│  大盘大宗交易统计                                        │
│  [溢折价率] [成交金额] [成交次数]                        │
│ ┌────────────────────────────────────────────────────┐ │
│ │  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇                        │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### 5.5 增发送配面板布局

```
┌────────────────────────────────────────────────────────┐
│  [全A][沪主板][科创板][深主板][创业板][北交所]            │
│  [全部] [分红预案] [已实施方案]                    [日期]│
│ ┌────────────────────────────────────────────────────┐ │
│ │ # | 代码 | 简称 | 送股 | 转股 | 派息 | 收益 |…      │ │
│ │   |      |      |      |      | (元) |      |…      │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### 5.6 机构持股面板布局

```
┌────────────────────────────────────────────────────────┐
│  [全部][北上][基金][保险][QFII][社保][券商][私募]...      │
│  [重仓] [增仓] [减仓] [新进] [不变]              [日期]  │
│ ┌────────────────────────────────────────────────────┐ │
│ │ # | 代码 | 简称 | 行业 | 机构数 | 持仓(万股) |…     │ │
│ │   |      |      |      |        | 市值(万) |…      │ │
│ │   | 占流通股% | 增减(万股) | 仓位类型 | 明细 |      │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────
```

---

## 6. PG 缓存策略

所有 Phase 9 端点通过 `CacheManager.fetch()` 接入 PG 缓存：

| 数据 | 缓存 key | TTL |
|------|---------|-----|
| 增减持 | `{market}:insider_change:{date}` | 交易日 4h / 盘后 24h |
| 大宗交易 | `block_trade:{date}` / `block_industry:{month}` | 当日 1h / 月度 24h |
| 增发送配 | `dividend:{date}:{market}:{status}` | 24h |
| 业绩预告 | `earnings:{date}:{type}` | 24h |
| 分析师评级 | `analyst:{date}:{period}` | 6h |
| 机构持股 | `inst_hold:{report_date}:{type}:{position}` | 72h（季报数据变化慢） |

---

## 7. 工单拆分

| 工单 | 内容 | 依赖 | 预估 |
|------|------|------|------|
| 9.01 | 大宗交易模块 `block_trade.py` + 解析器 | - | 1d |
| 9.02 | 增发送配模块 `dividend_bonus.py` + 解析器 | - | 0.5d |
| 9.03 | 业绩预告/快报模块 `earnings_forecast.py` | - | 0.5d |
| 9.04 | 分析师评级模块 `analyst_rating.py` | - | 0.5d |
| 9.05 | 机构持股模块 `institutional_hold.py` | - | 0.5d |
| 9.06 | 增减持图表增强（扩展现有 `insider_transactions.py`） | - | 0.5d |
| 9.07 | FEATURE_TABLE 注册 7 个新 feature + PG 缓存 | 9.01-9.06 | 0.5d |
| 9.08 | GUI: BlockTradePanel（明细表 + 行业图 + 统计图） | 9.01 | 1d |
| 9.09 | GUI: DividendBonusPanel | 9.02 | 0.5d |
| 9.10 | GUI: EarningsForecastPanel | 9.03 | 0.5d |
| 9.11 | GUI: AnalystRatingPanel | 9.04 | 0.5d |
| 9.12 | GUI: InstitutionalHoldPanel | 9.05 | 0.5d |
| 9.13 | GUI: InsiderTransactionsPanel 增强（增减持图表） | 9.06 | 0.5d |
| 9.14 | AstockFeatureTabs 注册新面板 | 9.08-9.13 | 0.5d |
| 9.15 | 快照测试 + 集成测试 | 全部 | 0.5d |

**总计**：约 8 个工作日

---

## 8. 验收标准

### 增持减持
- [ ] `get_insider_change_chart()` 返回月度增减持柱状图 markdown
- [ ] InsiderTransactionsPanel 新增 ECharts 柱状图区域
- [ ] 市场筛选 Tab（全A/沪/深/创/科/北）

### 大宗交易
- [ ] `get_block_trade_detail()` 返回个股大宗交易明细
- [ ] `get_block_trade_industry()` 返回行业分布数据
- [ ] `get_block_trade_market_stat()` 返回大盘统计数据
- [ ] BlockTradePanel 三区域渲染：明细表 + 行业分布图 + 大盘统计图
- [ ] 营业部买入/卖出名称红色/绿色标注

### 增发送配
- [ ] `get_dividend_bonus()` 返回分红送转方案明细
- [ ] DividendBonusPanel 渲染表格（送股/转股/派息/公告日/除权日/进度）
- [ ] 市场筛选 + 状态筛选（预案/已实施）

### 财报数据
- [ ] `get_earnings_forecast()` 返回业绩预告
- [ ] `get_earnings_express()` 返回业绩快报
- [ ] EarningsForecastPanel 多 Tab（预告/快报/披露时间）

### 价值分析
- [ ] `get_analyst_rating()` 返回分析师评级/目标价/EPS预测
- [ ] AnalystRatingPanel 渲染评级表格

### 机构持股
- [ ] `get_institutional_hold()` 返回机构持仓明细
- [ ] InstitutionalHoldPanel 多 Tab（全部/北上/基金/保险/QFII…）+ 仓位筛选（重仓/增仓/减仓/新进/不变）

### 通用
- [ ] 每个 feature 在 FEATURE_TABLE 注册
- [ ] 每个端点接入 PG 缓存（CacheManager.fetch）
- [ ] TypeScript 编译 0 错误
- [ ] 快照测试覆盖每个解析器

---

*文档基于 2026-09-04 通达信截图 + akshare 接口调研编写。*
