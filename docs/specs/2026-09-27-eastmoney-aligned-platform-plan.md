# TradingAgents 平台方案（对标东方财富）

> 日期：2026-09-27 ｜ 状态：**方案（待评审）**
> 参考系：**东方财富**为主（数据中心广度），**通达信**降为交互层参考
> 前序文档：`docs/specs/2026-08-29-tdx-style-platform-design.md`（TDX 交互框架，保留）
> 共享词汇/事实基线：根目录 `CONTEXT.md`

---

## 0. 决策摘要（本轮采用默认，可推翻）

访谈第一轮未收到逐题回答，按「继续」推进，采用以下默认决策：

| # | 决策 | 取值 |
|---|------|------|
| D1 | 交付物 | 本方案文档 → 评审后 `/to-tickets` 拆工单 |
| D2 | 参考系 | EM 主（数据中心广度）、TDX 次（看盘交互） |
| D3 | 范围 | 聚焦 6 引擎做深：资金流 / 持仓股东 / 公司行动 / 事件 / 基本面+预期 / 资讯公告日历；行情与 AI 不重建 |
| D4 | 节奏 | 先「接通与清理」，再按引擎竖切 tracer bullet |
| D5 | 旧文档 | 本方案引用并裁决，旧文档加指向行、不删 |
| D6 | 变更安全 | **不删数据/文件；不确定不擅自改；删除/覆盖先确认**（见 §0.1） |

### 0.1 变更安全守则（硬约束）

1. **只增不删**：孤儿组件、stub feature、旧文档、akshare 路径一律保留；清理用「归档目录 / 标注 `@deprecated` / 文档指向」，不用删除。
2. **不确定不改**：行为变更（含 `hk_ipo` 数据错标、渲染器统一）先提出方案、等确认；未确认前只做增量操作（注释、指向行、测试），不改现有逻辑与数据。
3. **删除/覆盖须显式授权**：任何 `rm`、注册表移除、数据清空，须用户逐项确认后执行。
4. **数据落盘不可逆**：PG/SQLite/TDengine/`.scratch` 历史只追加；缓存清理走既有 `CacheManager.clear` 语义，不手工删库。


---

## 1. 目标

把平台从「**TDX 看盘交互已较完整、EM 数据中心大面积 passthrough**」推进到「**EM 级数据中心广度 + 结构化渲染 + 单一条数据路径**」。

一句话验收：`FEATURE_TABLE` 的每个 key，**后端有真数据、前端有结构化渲染、两端 key 对等**。

---

## 2. 现状事实（已验证，2026-09-27）

### 2.1 后端
- `FEATURE_TABLE` **53 key**（`tradingagents_api/astock_features.py:1480-1547`）：**12 个结构化 parser**，**41 个 passthrough**（仅 raw markdown）。
- 统一端点 `POST /api/astock-features`（body `feature/ticker/date/params`），`GET /api/stock-info/{ticker}`。
- 另有独立 router：`market_overview.py`（`GET /api/market-overview`）、`hot_stocks.py`。

### 2.2 stub / 假数据（5 个）
| feature | 问题 | 位置 |
|---|---|---|
| `neeq_abnormal_trade` | 静态「无公开 API」 | `tdx_reference.py:24-70` |
| `us_ipo` | 静态「无公开 API」 | `tdx_reference.py:159-208` |
| `hk_ipo` | **返回 A 股 IPO 数据**（错标） | `tdx_reference.py:104-113` |
| `st_changes` | 静态「ReportName 未确认」 | `survey_reference.py:248-276` |
| `company_name_changes` | 非数据功能，硬编码 demo | `survey_reference.py:165-243` |

### 2.3 前端不可达 / 渲染回退
- `AstockFeatureTabs` 只注册 **12** Tab（`types.ts:651-664`）；`FeatureRenderer` 已实现 `block_trade_*`/`dividend_bonus`/`earnings_forecast|express`/`analyst_rating`/`institutional_hold` 分支（`AstockFeatureTabs.tsx:206-221`）→ **5 个面板无注册 key，不可达**。
- `MarketOverviewPage` 21 Tab 中 **20 个** `MarkdownRenderer(raw_md)`。
- Phase 9 五面板**仅 rawMd**，无结构化字段。
- 两套 markdown 渲染并存（自研 `MarkdownRenderer` 23 处 vs `react-markdown` 报告页）。
- **孤儿组件**：`ReportCharts.tsx` + `charts/{Kline,Macd,Rsi,Bollinger,SignalDashboard,FundFlow}Chart`；`astock/MarkdownTable.tsx`；`tradingview/DrawingManager.ts`；`shared/index.ts`+`shared/DataTable.tsx`。

### 2.4 数据路径分裂
- `eastmoney.py`：`datacenter-web` 直连 + 反爬节流（`_em_get`/`_eastmoney_datacenter`）。
- `eastmoney_client.py`：分策略绕 TLS 指纹（push2 IP 直连 / datacenter curl_cffi）。
- **Phase 9 五模块走 akshare**（`_safe_akshare_call`），不经 `eastmoney.py` → 同一份东财数据两条路径、两套错误处理。
- 缓存：`CacheManager.fetch(feature, key, source_fn=...)` 统一入口，PG+SQLite+TTL（`tradingagents/cache/manager.py:510`），Phase 9 已接入。

### 2.5 文档/工单
- `docs/specs/` Phase 5–9（7/8/9 仍标「提案」）；`docs/GAP_ANALYSIS.md` 的 P0 已在代码层绕过但未回标。
- 工单：本地 `.scratch/<feature>/issues/*.md`。
- 无 `CONTEXT.md`/`AGENTS.md`（本方案同时建立 `CONTEXT.md`）。

---

## 3. 东方财富能力对标矩阵

图例：**✅ 已有结构化** ｜ **⚠️ 已实现但不可达/仅 rawMd** ｜ **🕳 未实现** ｜ **— 不纳入**

| # | EM 引擎 | 现有 feature（本平台） | 状态 | 目标 |
|---|---------|------------------------|------|------|
| 1 | 行情 | realtime-prices / chart-data / market-overview / `stock_info_panel` | ✅ | 维持；`stock_info_panel` 结构化 |
| 2 | 资金流 | `northbound_flow`、`concept_blocks`（部分）、`hot_stocks` | ⚠️ | 补主力/超大单个股与行业概念资金流（`RPT_INDUSTRY_FUNDFLOW` 等） |
| 3 | 持仓股东 | `insider_transactions`、`insider_change_chart`、`survey_interaction`、`institutional_hold`、`chip_distribution` | ⚠️ | `institutional_hold` 接通；补股东户数 / 十大股东 / 十大流通 / 重要机构（社保险资） |
| 4 | 公司行动 | `dividend_bonus`、`lockup_expiry`、`block_trade_*` | ⚠️ | 接通；补回购 / 股权质押 / 商誉 / 增发配股 |
| 5 | 事件 | `dragon_tiger`、`margin_*`、`block_trade_*`、`futures_position`、`seat_activity`、`investment_calendar` | ⚠️ | 接通两融；补股东大会 / 重大合同 / 关联交易 / 研报席位 |
| 6 | 基本面 | `balance_sheet`/`cashflow`/`income_statement`、`earnings_forecast`/`express`、`profit_forecast` | ⚠️ | 接通预告/快报；补财务指标（MAINFINADATA） |
| 7 | 预期 | `profit_forecast`、`analyst_rating` | ⚠️ | 接通评级；补研报流（`reportapi`）+ 一致预期明细 |
| 8 | IPO/转债/期货/期权 | `ipo_declaration`/`ipo_listing`、`futures_position`、`hk_ipo`/`us_ipo`/`neeq` | ⚠️🕳 | 修 `hk_ipo`（真港股）、裁定 `us_ipo`/`neeq`/`st_changes`；补可转债、期权龙虎榜 |
| 9 | 选股器 | `screener.py`（条件+模板+NL） | ✅ | 维持；底层字段接引擎 2–6 |
| 10 | 资讯公告日历 | NewsFeed、`stock_info_panel` 公告、`investment_calendar` | ⚠️ | 补研报中心 / 财报日历 / 股吧人气 |
| 11 | 组合/自选/预警 | `portfolio`、`watchlist`、`alerts`（本地优先） | ✅ | 维持（登录态数据不做） |
| 12 | AI | 多智能体研究 + 决策回测 | ✅ 独有 | 不重建 |

其它既有：`fund_*`（4）、`industry_*`（6）、`macro_*`（4）、`market_statistics`、`survey_interaction`、`company_name_changes`/`st_changes`。

---

## 4. 目标架构（三层契约）

```
┌ 数据模块层  tradingagents/dataflows/a_stock/*.py ─────────────┐
│ 统一走 eastmoney.py 直连（datacenter-web / push2）             │
│ 新增功能以直连为主；akshare 作 fallback（存量调用保留）        │
└──────────────────────────────┬───────────────────────────────┘
                               │ 返回结构化 dict/list（非 markdown）
┌ feature 注册层  astock_features.py FEATURE_TABLE ────────────┐
│ key → {call, parser, params_schema, cache_ttl}                │
│ parser 必须是 _parse_*（输出 JSON 字段）                      │
│ raw 输出降级为显式 kind="raw" 类型，计入技术债而非默认        │
└──────────────────────────────┬───────────────────────────────┘
                               │ 统一 payload: {columns, rows, meta} 或 {raw}
┌ 渲染层  tradingagents_gui ────────────────────────────────────┐
│ 单一 GenericDataTable 渲染 {columns, rows}；面板只做列定义/样式│
│ 单一 markdown 渲染器（保留 react-markdown，退役自研）          │
└───────────────────────────────────────────────────────────────┘
```

**核心不变量**
1. `FEATURE_TABLE` 与 `ASTOCK_FEATURE_TABS` **key 集合对等**（加对等性测试）。
2. 每个 feature 声明的 parser 类型 ∈ {structured, raw}；`raw` 必须在方案 §9 技术债清单登记。
3. 数据模块不返回「给人看的 markdown」，返回结构化数据；markdown 只在渲染层生成。

---

## 5. 数据源策略

| 层 | 选择 | 理由 |
|---|---|---|
| 主 | `eastmoney.py` 直连 `datacenter-web`（reportName）+ `push2` | 无 akshare 版本波动、可控 reportName/字段、已有节流与重试 |
| 兜底 | akshare | akshare 断供/字段变动时降级 |
| 存量 | `_safe_akshare_call` 仅作为**新 feature 的 fallback 分支**；**不删除现有调用** | 消除「新增双路径」；存量代码保留，待对应功能验证通过后再由用户决定是否收敛 |

> 已核实开放无鉴权端点：`datacenter-web.eastmoney.com/api/data/v1/get`（约 40 reportName，含 `RPT_INDUSTRY_FUNDFLOW` / `RPT_HOLDERNUMLATEST` / `RPT_SHARE_HOLDER_INCREASE` / `RPT_LICO_FN_CPD` / `RPT_PUBLIC_OP_NEWPREDICT` / `RPT_WEB_RESPREDICT` / `RPT_F10_*` 等）、`datacenter.eastmoney.com/securities/api/data/v1/get`（F10）、`reportapi.eastmoney.com/report/list`。已知故障：`9701 繁忙`（重试）、`9501 配置不存在`（reportName 错）。

### 5.1 存储分工（记录现状 + 新规）

现状（口口相传，此前未文档化）：

| 存储 | 职责 | 证据 |
|---|---|---|
| **PostgreSQL** | 缓存（`CacheManager`，SQLite 本地 + PG 共享）+ `data_history` **永久归档**（不随 TTL/清缓存删除） | `tradingagents/cache/manager.py:413-468` |
| **TDengine** | 分钟级时序（K线分钟线，超级表 + 每股票子表） | `tradingagents_api/chart_data/fetchers.py:262-331` |

**新规（Phase 12 起）**：新增引擎（资金流/持仓股东/公司行动/事件/基本面/预期）均为**低频报表数据**，一律走 **PG 缓存 + `data_history` 归档**，**不进 TDengine**。理由：时序库适合高频等间隔点，报表数据按报告期/交易日稀疏发布，塞入会污染 schema 且无查询收益。

> 本分工与工单 12 对应；`CONTEXT.md` 术语表同步记录。

---

## 6. 路线图

### Phase 10 — 接通与清理（低成本见效）
| 工单 | 内容 | 依赖 |
|---|---|---|
| 10.01 | 注册 5 个 Phase 9 面板进 `ASTOCK_FEATURE_TABS` + `MarketOverviewPage` Tab | — |
| 10.02 | 5 个 Phase 9 feature 结构化 parser（`{columns,rows}`） | 10.01 |
| 10.03 | `hk_ipo` 数据错标（返回 A 股）修复方案先行评审；`us_ipo`/`neeq`/`st_changes`/`company_name_changes` 收敛（接真源 或 标注「暂不提供」+ 前端显式提示，**不删 key、不删函数**） | — |
| 10.04 | 统一 markdown 渲染：先对拍再切；自研 `MarkdownRenderer` **保留并标注 `@deprecated`**，不删文件；移除调试 log（`TradingViewLayout.tsx:334`） | — |
| 10.05 | 孤儿组件处置：**优先复活**（`ReportCharts` 系列进报告页；`shared/DataTable` 提升为通用表）；确需停用的移入 `src/components/_archive/` 并标注，不删 | — |
| 10.06 | 回标 `docs/GAP_ANALYSIS.md`（P0 已解决） | — |

### Phase 11 — 渲染契约统一
| 工单 | 内容 | 依赖 |
|---|---|---|
| 11.01 | 定义统一 feature payload 类型（`types.ts`）+ 后端 `{columns,rows,meta}` 约定 | — |
| 11.02 | `GenericDataTable` 组件（列定义驱动），12 个结构化面板迁移 | 11.01 |
| 11.03 | `kind=raw` 显式类型 + 技术债登记 + 前后端 key 对等性测试 | 11.01 |

### Phase 12 — EM 引擎补齐（数据广度，竖切到底）
| 工单 | 引擎 | 内容 |
|---|---|---|
| 12.01 | 资金流 | 个股/行业/概念主力净流入（`RPT_INDUSTRY_FUNDFLOW` + push2 clist） |
| 12.02 | 持仓股东 | 股东户数、十大股东/十大流通、重要机构持股 |
| 12.03 | 公司行动 | 股票回购、股权质押、商誉、增发配股 |
| 12.04 | 事件 | 股东大会、重大合同、关联交易 |
| 12.05 | 预期 | 研报流（`reportapi`）、一致预期明细（`RPT_VALUEANALYSIS_DET`） |
| 12.06 | 其它品种 | 可转债列表、期权龙虎榜 |

每个工单：数据函数（EM 直连）→ `_parse_*` → 面板 → 注册 → 快照测试。

### Phase 13 — 资讯/日历/选股器联动
研报中心 / 财报日历 / 股吧人气接入；选股器字段扩到引擎 2–6。

### Phase 14 — 验收与文档
全量 key 对等测试、快照测试、`docs/FEATURES.md` 重写为 EM 对照口径。

---

## 7. 验收标准

- [ ] `FEATURE_TABLE` 与 `ASTOCK_FEATURE_TABS` key 集合相等（自动化测试）
- [ ] 5 个 Phase 9 面板经个股 Tab 与市场页**均可达**且有结构化渲染
- [ ] 5 个 stub 收敛：真数据 或 显式「暂不提供」（key/函数保留）
- [ ] 单一活跃 markdown 渲染器；自研渲染器已 `@deprecated` 且无生产引用
- [ ] 孤儿组件全部复活或移入 `_archive/`（**无删除**）
- [ ] 新代码无 akshare-only 路径（存量调用保留，收敛另行确认）
- [ ] `tsc` 0 错误；pytest 全绿；新增快照覆盖每个新增 parser
- [ ] 全程未删除任何数据文件、旧文档、组件文件

---

## 8. 风险与开放项

| 风险 | 缓解 |
|---|---|
| 东财 `9701` 限流 / 反爬升级 | 复用 `eastmoney.py` 节流 + `eastmoney_client.py` 指纹绕过；akshare fallback |
| akshare 与直连字段漂移 | 统一走直连，akshare 仅 fallback，避免长期双维护 |
| 结构化 parser 工作量（41 个 → 0 raw） | Phase 12 分批，每批 3–6 feature，可独立验收 |
| 前端两套 md 渲染退役有回归风险 | **不删**：自研渲染器标注 `@deprecated` 保留，先对拍、按 key 逐个切换，出问题可切回 |
| 旧文档（Phase 7/8/9）与新方案冲突 | 本方案逐条裁决表（§3 + §6），旧文档加指向行、**不删** |

**未决（待用户裁决）**
1. 数据源是否接受「新增直连为主、akshare 兜底；存量 akshare 调用暂不动」（D-数据源）？
2. `us_ipo`/`neeq`/`st_changes`/`company_name_changes`：接真源、还是标注「暂不提供」？（**均不移除 key/函数**）
3. 孤儿 `ReportCharts` 系列：优先复活进报告页；确不复活则移入 `_archive/` 而非删除 —— 是否同意？
4. Phase 12 的 6 个引擎优先级顺序（默认按上表 12.01→12.06）。

---

*本方案基于 2026-09-27 代码库事实 + 东方财富开放端点实地核查编写；工单在评审后经 `/to-tickets` 生成。*
