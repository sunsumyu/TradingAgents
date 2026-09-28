# CONTEXT — TradingAgents（A股研究/看盘平台）

> 本文件是**共享词汇表 + 已验证事实**的单一事实源。决策记录见 `docs/adr/`（如有）。
> 建立于 2026-09-27，用于「参考东方财富重定项目方案」的访谈基线。
> **只记录已验证的事实与已确认的决策**；未决问题在下节列出。

---

## 1. 产品身份

TradingAgents 是一套二合一平台：

- **看盘/终端侧**：对标通达信（TDX）——K线多周期、技术指标、画线、选股器、预警、模拟组合。
- **分析侧（独有）**：多智能体 LLM 研究（分析师 + 辩论）→ 结构化交易决策报告 → 可回测。

技术构成：FastAPI 后端 `tradingagents_api/`；数据层 `tradingagents/dataflows/a_stock/`；React+TS+Vite GUI `tradingagents_gui/`。

**术语**
| 词 | 含义 |
|---|---|
| A股特色数据 | 平台把个股/市场数据按「feature」暴露的机制，见 `FEATURE_TABLE` |
| feature | `POST /api/astock-features` 的一个 `feature` 名，映射到后端函数 + 解析器 |
| 结构化解析器 | `_parse_*`，把后端 markdown 转成前端可渲染的 JSON 字段 |
| passthrough | `_passthrough_parser`，只回传 raw markdown，前端靠 `MarkdownRenderer` 兜底 |
| 数据中心 | 对标东方财富 `data.eastmoney.com` 的各类报表 |
| payload 契约 | 统一特征载荷 `{kind, columns, rows, provenance}`，见 `tradingagents_api/feature_payload.py` |
| `kind=raw` | 显式降级类型：承载未结构化的 markdown，计入技术债，非默认 |
| 存储分工 | PG：缓存 + `data_history` 永久归档（低频报表）；TDengine：分钟级时序 |

---

## 2b. 已交付（2026-09-27）

| 项 | 产物 |
|---|---|
| 对等性测试 | `tests/test_feature_key_parity.py` — **已转绿**（工单 07 后不变量修正为「前端 ⊆ 后端」：后端-only 是市场级 feature，属预期；3 passed） |
| payload 契约 | `tradingagents_api/feature_payload.py` + `tests/test_feature_payload.py`（6 绿） |
| 前端契约镜像 | `tradingagents_gui/src/lib/types.ts`（`FeaturePayloadEnvelope` + `formatFeatureCell`）+ `feature-payload.test.ts`（6 绿） |
| 文档回标 | `docs/GAP_ANALYSIS.md` P0 已解决标注；Phase 7/8/9 加指向行 |
| 存储分工 | 方案 §5.1（PG vs TDengine，新引擎走 PG） |
| 工单 06 | 8 个 Phase 9 结构化 parser（大宗×3/分红/业绩预告/快报/评级/机构持股）+ 62 parser 测试 |
| 工单 07 | 5 个 Phase 9 面板注册进个股 Tab（12→17）与市场页（markdown 回退→结构化面板）；分派器补传 `data` |
| 工单 03 | markdown 渲染器统一：`shared/Markdown`（react-markdown+remark-gfm+`prose-compact`）为唯一活跃实现；23 个调用点迁移；自研渲染器留 `@deprecated` 委托壳；对拍差异矩阵记录于测试文件头 |
| 工单 05 | `shared/GenericDataTable`（+`FeatureDataTable` 适配器，17 测试）；样板接入 `InstitutionalHoldPanel` |
| 工单 10 | 孤儿判定：复活 SignalDashboard/FundFlowChart 进报告页；8 个 0 引用文件移入 `src/_archive/`（未删除）；全仓重扫孤儿=0 |
| 工单 11 | TTL 分级落地：`register_feature_ttl` 注册表 + FEATURE_TABLE 声明（评级 6h/机构持股 72h/大宗当日 1h 等，Phase 9 规格 §6）；未声明者行为不变；7 测试 |
| 工单 08/09 | 数据源探测（实测）：hk_ipo 错标**现场核实**（akshare 返回 A 股代码段）；港/美 IPO、三板、ST 无东财报表（9501，对照组有效）；**深交所更名真源已探明**（简称变更 7482 行）。预授权分支已落地：`DataSourceNotice` 警示条上 hk/us/neeq/reference 四 Tab；换真源待裁决 |
| 工单 13 (12.01) | 板块资金流引擎：`RPT_INDUSTRY_FUNDFLOW`/`RPT_CONCEPT_FUNDFLOW` **实测核实**；`fund_flow_ranking.get_board_fund_flow` + 共用 parser + 2 个新 feature（TTL 1h）+ `FundFlowPanel`（行业/概念子页签）上市场页「资金」Tab；个股排名（push2 clist）本环境不可核验，留待生产验证 |
| 工单 14 (12.02) | 持仓股东引擎：`RPT_HOLDERNUMLATEST`（每股最新一期）/ `RPT_F10_EH_FREEHOLDERS`（securities F10）/ `RPT_SHARE_HOLDER_INCREASE` 三源**实测核实**（茅台案例交叉验证单位）；3 个新 feature（58 个）+ `HolderPanel` 三形态 + 个股 Tab 栏 3 个新 tab |
| 工单 15 (12.03) | 公司行动（部分）：质押 3 报表 + 回购报表 **页源抓取核实**（12 个猜测名全 9501 → 改抓 data.eastmoney.com 页面/JS 提取 RPT_*）；单位 row0 验算；4 新 feature（62 个）+ 质押/回购 Tab；商誉/增发无端点已登记 |
| 工单 18 (12.06) | 可转债：`RPT_BOND_CB_LIST` 实测核实（1059 只，页源提取+efinance 互证）；convert_bond_list feature（63 个）+ ConvertBondPanel + 「转债」Tab；一致预期报表 9701×3 已记录待核 |
| 工单 16 (12.04) | 公司公告：np-anotice `stock_list` 个股过滤实测核实（`codes=` 不过滤）；stock_notices feature（64 个，默认 TTL）+ StockNoticesPanel 列表渲染 + 个股 Tab「公告」；二级分类树待探测 |
| 工单 17 (12.05) | 研报流：reportapi `/report/list` 实测核实（全市场 7197 + 个股过滤 40，beginTime/endTime 必填）；research_reports feature（65 个，双模式 parser）+ ResearchReportsPanel + 个股 Tab「研报」；一致预期 RPT_VALUEANALYSIS_DET 9701×3 待核 |
| Phase 13 批次 | 宏观三件套结构化：`_parse_macro_gdp`（三表→MacroAnalysisPanel 转置格式 {gdp:{trend,growth,structure}}，e2e 12+12 条）/`_parse_macro_cpi`（25 条）/`_parse_macro_pmi`（15 条，ast.literal_eval dict 行）；SCHEMA_VERSIONS 升 2.1/2.2 失效旧缓存；`MacroAnalysisPanel` 新增 CPI/PMI 区块（GenericDataTable）+ 市场页接线 |
| Phase 13 批次 2 | 新股结构化：`_parse_ipo_declaration`（11 列）/`_parse_ipo_listing`（10 列，win_rate 百分数→小数）点亮既有 IpoCenterPanel 结构化分支；SCHEMA_VERSIONS 2.1 失效旧缓存；e2e 6+6 条 |
| Phase 13 批次 3 | 融资融券结构化：`_parse_margin_detail`（11 列，亿→元/万→股，e2e 50 条 market=沪市 total=2000）/`_parse_margin_market_stat`（6 列时序，30 条）点亮既有 MarginTradingPanel；`_parse_cn_quantity` 中文数量级解析器；SCHEMA 2.1 |
| Phase 13 批次 4 | 基金四项结构化：`_parse_fund_purchase`（保留 FundDataPanel 字段 + issuing/upcoming 分组）/`_parse_fund_announcement`+`_parse_fund_scale`（`_parse_fund_sections` 按 `##` 分组保留原始列）/`_parse_fund_open_info`；`_call_fund_*` 由 bullet 列表改为 markdown 表供解析；SCHEMA 2.1 |
| Phase 13 批次 5 | 投资日历 + 龙虎榜活跃度结构化：`_parse_investment_calendar`（五组事件，e2e 2026-09-24 首发上市/发行各 1 条；按内容而非缩进识别表头）/`_parse_seat_activity`（7 列，e2e 30 条）/`_parse_stock_activity`（6 列，e2e 30 条）；新建 `DragonActivityPanel`（席位/股票双表，FeatureDataTable）+ 市场页「龙虎」Tab 接线；SCHEMA 2.1/2.2 |
| Phase 13 批次 6 | 产业链 + 行业数据七项结构化：`_parse_industry_chain_categories/chains/overview`（分类树/卡片三分区/聚合，点亮 IndustryChainPanel 结构化分支）、`_parse_industry_list`（市值 亿→元）、`_parse_industry_commodity`（价格行+历史表）、`_parse_industry_data_overview`、`_parse_industry_detail`；`IndustryDataPanel` change_pct 空值保护；e2e 分类 10 大类/卡片 8+8+10/商品 WTI 83.53(+1.58%)；SCHEMA 2.1/2.2 |
| Phase 13 批次 7 | 调研/市场统计/股指期货结构化：`_parse_survey_interaction`（13 列，e2e 50 条）、`_parse_market_statistics`（规模 2+成交 5+投资者 1 三节）、`_parse_futures_position`（品种 IF 3 合约×3 榜单 20 行+本日合计）；新建 `MarketTablePanel` 通用小表组，市场页「统计」「调研」Tab 结构化接线（期货为嵌套合约结构留待专用面板，仍走 markdown）；SCHEMA 2.1 |
| Phase 13 批次 8（工单 09） | 备查资料接真源：`get_company_name_changes` 由新浪单股演示改为**深交所-名称变更真源**（实测简称变更 7482 行/全称变更 1762 行，日期窗口过滤+分页，仅深市）；`get_st_changes` 由占位提示改为**简称变更派生**（变更后含 ST→实施/变更前含→撤销/双含→调整），e2e 近 90 天更名 53 条、ST 派生 21 条（首条 2026-09-28 易联众 ST→撤销）；`_parse_company_name_changes`/`_parse_st_changes` 结构化；前端备查 Tab DataSourceNotice 文案更新为 partial；SCHEMA 2.1 |
| Phase 14（工单 04+文档） | `docs/FEATURES.md` §8 重写为 **EM 对照口径**：65 feature 按 4 组分表（个股 15/市场全景-新股-融资-日历-龙虎 9/公司行动-财报-价值-资金流 11/通达信数据菜单 17+3），逐项标注数据源+面板+结构化状态；§11 API 计数、§12 TDX 对照表（新股/融资/日历/活跃度 → ✅）、§13 差距表（14 条陈旧项 → 11 条真实差距，历史差距标注已消除）同步修正；文档头改「对标东方财富+通达信」双参考系；akshare 探测确认港股 IPO 无可用函数（stock_ipo_hk_ths 即错标源），工单 08 维持待裁决；工单 04 核验关闭 |
| 工单台账核验（2026-09-28） | 01/02/04/06/07/12 六张实际已完成但状态滞留的工单核验关闭（对等性测试 3 passed、payload 契约模块+6 测试、Phase 9 七 feature 全结构化、五面板两端注册、存储分工 §5.1 已在） |
| 工单 16 余项：公告分类树 | np-anotice 官方二级分类树**实测拿到**（源：notices 页 HTML 过滤器元素）：f_node 0-7（财务报告/融资公告/风险提示/信息变更/重大事项/资产重组/持股变动）× s_node 0-13（定期报告…利润分配）；**修正原假设：股东大会/关联交易不在过滤节点中**；组合过滤 e2e 验证（600519 f1s1 定期报告 5 条/f1s5 业绩预告 1 条/f5s7 重大合同 0 条）；`get_stock_notices` 接入 f_node/s_node params 透传，分类树登记于模块 docstring |
| 工单 08/13 终局探测（2026-09-28） | **hk_ipo**：`xg/hk/` 页面已 404 下线，存活 `/xg/` 全量 JS 仅含 A 股报表名（RPTA_APP_IPOAPPLY 等 5 个），8 个 RPT_HK_* 定向猜测全空——**东财通道彻底关闭**，真源只剩港交所披露易/阿斯达克（新站抓取，待裁决）；**个股排名**：push2 全系主机（含 delay/his 镜像）本环境网络层阻断（requests 与 curl_cffi 一致），确证环境限制，留待生产验证 |
| 工单 14 余项：股东户数历史 | `RPT_HOLDERNUM_DET` 探测成功（600519 实测 30+ 期，含户均持股数/户均市值/区间涨跌幅，量纲自洽 4217 股×1185.49 元≈500 万）；`get_holder_num` 换源，markdown 5 列结构不变 → parser/面板零改动；SCHEMA 2.2（首次 e2e 网络抖动缓存空结果，再升版本失效）；e2e 50 期（2026-06-30 296,404 户 +21.9% → 2015-09-30 46,869 户）；特征测试组 140 passed |
| 工单 17 余项：一致预期接入 | **报表名修正**：`RPT_VALUEANALYSIS_DET`（原 9701 待核项）实为估值分析明细（带个股过滤可达，PE/PB/PS/PEG），非一致预期；真身 = **`RPT_WEB_RESPREDICT`**（从 akshare 源码反查，需具名列组 `columns=WEB_RESPREDICT` + 排序 RATING_ORG_NUM，此前 9701 根因即参数形态）；三种过滤实测 code=0（全市场 587 页/行业/个股）；新模块 `consensus_estimate.py` + 第 66 个 feature key（TTL 24h）+ `_parse_consensus_estimate`（14 列）；e2e 个股 600519 → 43 机构 34 买入、目标价 1430–2030 元、2025A EPS 65.85/2026E 67.25，市场模式 Top3 茅台 43/东鹏 41/伊利 38；特征测试组 **142 passed**；66 feature 中 passthrough 7 |
| 工单 08 关闭：hk_ipo 换源 aastocks | aastocks 新股主页可达（215KB 结构化表）、新浪港股页 JS 壳、HKEX 404；`get_hk_ipo` 重写为 aastocks 抓取（正在招股 + 半新股已上市，过滤 @ 衍生权证行、剥离「跌穿上市价」后缀、日期归一 ISO）；`_parse_hk_ipo` 双分区注册（**passthrough 7 → 6**）；SCHEMA 2.1；e2e 招股中 1 只（奕斯伟 01256 招股价 1.48-1.59 入场费 3212.07 截止 2026-10-06）+ 已上市 16 只（纳真 09856/星环 06727/优地 03231），全 5 位港股码；`TestHkIpoParse` 落实票内「断言非 A 股代码」验收（**144 passed**）；前端港股 Tab 警示 mislabel → partial。**18 张工单全部关闭** |

**前端测试：** `vitest run` 8 文件 **130 passed**；`npm run build`（含 tsc）通过。
**后端测试：** parser/payload/parity/ttl 套件 **140 passed**（Phase 13 批次 1–8 累计新增 50 个）；全量 1232 passed + 16 个**既有**失败（test_data_cache/env_overrides/portfolio，与本次工作无关）。
**Phase 13 收敛结果：** FEATURE_TABLE 65 项中 passthrough 由 26 → **7**；剩余 7 项全部为 (a) 待裁决工单 08/09 余项（hk_ipo 数据错标、us_ipo/neeq 无公开源）或 (b) 无前端消费者/后端本身无数据（margin_industry 概览占位、macro_overview 复合、stock_info_panel、insider_change_chart），结构化需先接真源或定用途。

---

## 2. 参考产品与数据源（已验证）

### 2.1 数据源现实
- 生产数据主要来自 **东方财富**（`datacenter-web.eastmoney.com/api/data/v1/get` 的 `reportName` 报表、`push2/push2his` 行情），辅以腾讯/新浪/同花顺/akshare/mootdx/baostock。
- 反爬：`eastmoney.py` 有节流 + UA + 重试；`eastmoney_client.py` 分策略绕 TLS 指纹；`.env` 有代理绕过。
- 已知故障模式：东财 `code:9701 服务器繁忙`（可重试）、`code:9501 报表配置不存在`（reportName 错）。

### 2.2 东方财富的能力面（用于对标，来源：实地抓取）
分 12 组：行情引擎、资金流、持仓/股东、公司行动、事件（龙虎榜/大宗/两融/调研）、基本面（业绩/三表）、预期（评级/一致预期）、IPO/转债/期货/期权、选股器、资讯公告日历、组合/自选/预警（登录态）、AI（妙想/Choice）。
- 开放无鉴权可抓：`datacenter-web` 约 40 张报表、`datacenter.eastmoney.com/securities`（F10）、`push2*` 行情、`np-anotice-stock`/`reportapi`/`np-listapi`、`fund.eastmoney.com`、`emappdata`。
- 登录态：自选/组合/预警/股吧。
- 付费 🔒：Choice QuantAPI、Level-2。

### 2.3 通达信参考面
现有 `docs/specs/2026-08-29-tdx-style-platform-design.md` 等按 TDX 终端功能对标。

---

## 3. 当前实现状态（已验证，2026-09-27）

### 3.1 后端 feature 面
`FEATURE_TABLE` 共 **53** 个 key（`tradingagents_api/astock_features.py:1480-1547`）：
- **12** 个走结构化 `_parse_*`：`chip_distribution` `dragon_tiger` `northbound_flow` `concept_blocks` `profit_forecast` `lockup_expiry` `industry_comparison` `hot_stocks` `insider_transactions` `balance_sheet` `cashflow` `income_statement`。
- **41** 个走 `_passthrough_parser`（仅 raw markdown）。

端点：`POST /api/astock-features`（body: `feature/ticker/date/params`）；`GET /api/stock-info/{ticker}`。

### 3.2 明确为 stub / 假数据的功能
| feature | 问题 | 位置 |
|---|---|---|
| `neeq_abnormal_trade` | 静态文本「无公开 API」 | `tdx_reference.py:24-70` |
| `us_ipo` | 静态文本「无公开 API」 | `tdx_reference.py:159-208` |
| `hk_ipo` | 调 akshare 但**返回的是 A 股 IPO 数据**（错标） | `tdx_reference.py:104-113` |
| `st_changes` | 静态文本「ReportName 未确认」 | `survey_reference.py:248-276` |
| `company_name_changes` | 非数据功能，硬编码 demo | `survey_reference.py:165-243` |
| `survey_interaction` | ✅ 真实（`RPT_ORG_SURVEYNEW`） | `survey_reference.py:24-160` |

### 3.3 前端不可达 / 回退
- `AstockFeatureTabs` 只注册 **12** 个 Tab；但 `FeatureRenderer` 已实现 `block_trade_*`/`dividend_bonus`/`earnings_forecast|express`/`analyst_rating`/`institutional_hold` 的渲染分支 → **这 5 个 Phase 9 面板无注册 key，经个股 Tab 不可达**（`AstockFeatureTabs.tsx:206-221` vs `types.ts:651-664`）。
- `MarketOverviewPage` 21 个 Tab 中 **20 个**走 `MarkdownRenderer(raw_md)` 兜底。
- Phase 9 五个面板（BlockTrade/DividendBonus/EarningsForecast/AnalystRating/InstitutionalHold）**仅 rawMd 渲染**，无结构化字段。
- 存在两套 markdown 渲染：自研 `MarkdownRenderer`（23 处）与 `react-markdown`（报告页）。
- **孤儿组件**：`ReportCharts.tsx` 及其引用的 `charts/KlineChart|MacdChart|RsiChart|BollingerChart|SignalDashboard|FundFlowChart`；`astock/MarkdownTable.tsx`；`tradingview/DrawingManager.ts`；`shared/index.ts` + `shared/DataTable.tsx`。

### 3.4 RightInfoPanel（GAP_ANALYSIS P0）
- 现状：自行 5s 轮询 `POST /api/realtime-prices` + 一次性 `GET /api/stock-info/{ticker}`，**已绕过** prop-undefined 根因；`docs/GAP_ANALYSIS.md` 的「6 项数据不显示」未回标为已修复。
- 残留：`TradingViewLayout.tsx:334-335` 仍有调试 `console.log`。

### 3.5 文档与工单
- 方案文档：`docs/specs/`（Phase 5–9，其中 7/8/9 仍标「提案」）。
- 工单：本地文件制 `.scratch/<feature>/issues/*.md`（如 `report-visualization`、`tradingview-phase34`）。
- 无 `CONTEXT.md` / `AGENTS.md`（本文件为新建立）。
- 远端：`origin`=TauricResearch（上游）、`fork`=sunsumyu、`astock`=simonlin1212。提交信息引用 `#6`–`#14`，追踪器归属待确认。

---

## 4. 已确认决策（2026-09-27 访谈第一轮，采用默认）

| # | 决策 | 取值 |
|---|------|------|
| D1 | 交付物 | 方案文档 `docs/specs/2026-09-27-eastmoney-aligned-platform-plan.md`；评审后 `/to-tickets` |
| D2 | 参考系 | 东方财富为主（数据中心广度）；通达信降为交互层参考 |
| D3 | 范围 | 聚焦 6 引擎做深：资金流/持仓股东/公司行动/事件/基本面+预期/资讯公告日历；行情、AI 不重建 |
| D4 | 节奏 | 先 Phase 10「接通与清理」，后 Phase 12 按引擎竖切 |
| D5 | 旧文档 | 新方案引用并裁决，旧文档加指向行、不删 |
| D6 | 数据源 | `eastmoney.py` 直连为主，akshare 仅 fallback |
| D7 | 变更安全 | **不删数据/文件；不确定不擅自改；删除/覆盖先确认**（硬约束） |

## 6. 工单（Phase 10–11）

已发布至 `.scratch/eastmoney-align/issues/`，共 12 张（blockers-first 编号）：

| # | 标题 | Blocked by |
|---|------|-----------|
| 01 | 前后端 feature key 对等性测试 | — |
| 02 | 统一 feature payload 契约 | — |
| 03 | markdown 渲染器统一 | — |
| 04 | 旧文档口径回标 | — |
| 05 | 通用表渲染组件 `GenericDataTable` | 02 |
| 06 | 5 个 Phase 9 feature 结构化 parser | 02 |
| 07 | 注册 5 个 Phase 9 面板 | 06 |
| 08 | `hk_ipo` 数据错标修复 | —（待裁决） |
| 09 | stub feature 收敛 | —（待裁决） |
| 10 | 孤儿组件复活/归档 | 05 |
| 11 | 缓存 TTL 分级 | 02（待裁决） |
| 12 | 存储分工文档化（PG vs TDengine） | — |

Phase 12（EM 引擎补齐）待 Q9 定序后再拆。

## 7. 未决（待用户裁决）
1. ~~`company_name_changes`/`st_changes` 接真源~~ → **已完成（批次 8）**：深交所名称变更真源 + ST 派生。剩余 `us_ipo`/`neeq`：已实测东财 datacenter 无对应 reportName，接真源需引入港交所/阿斯达克等新站抓取，维持「暂不提供」警示 → 工单 09 余项
2. 孤儿 `ReportCharts` 系列：复活进报告页，或移入 `_archive/`？（不删除）→ 工单 10
3. Phase 12 六个引擎的优先级顺序？→ 待拆
4. `hk_ipo` 修复方向（真源 vs 显式警示）？→ 工单 08
5. 缓存 TTL 是否分级实施？→ 工单 11
