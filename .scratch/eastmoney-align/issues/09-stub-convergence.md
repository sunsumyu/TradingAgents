# 09 — stub feature 收敛（不删 key/函数）

**What to build:** 4 个 stub feature（`us_ipo`、`neeq_abnormal_trade`、`st_changes`、`company_name_changes`）当前返回静态文本或非数据 demo。按用户裁决收敛为：**接真源**，或**标注「暂不提供」并在前端显式提示**。无论哪种，**key 与后端函数一律保留**，不从注册表移除。

**Blocked by:** None — can start immediately. ⚠️ 收敛口径待用户裁决

**Status:** ✅ DONE (2026-09-28，Phase 13 批次 8) — 有真源者已接入，无真源者维持显式警示

- [x] 逐项核查是否存在可核实的真实数据源（东财 reportName 优先）
- [x] 有真源者接入；无真源者返回显式「暂不提供」结构（含原因），前端展示提示而非空表
- [x] `company_name_changes` 的非数据 demo 改为真实的公司更名查询或标注为文档条目
- [x] 不删任何 key、函数、模块
- [x] 在方案技术债清单登记处置结果


---

## 探测记录 (2026-09-27，实测)

| feature | 探测结果 | 结论 |
|---|---|---|
| `us_ipo` | 东财 reportName `RPT_USIPO_DETAIL`/`RPT_US_IPO` 均 9501；akshare 无美股 IPO 函数 | 无真源 → 显式警示已加 |
| `neeq_abnormal_trade` | `RPT_NEIQ_TRADE`/`RPT_NEEQ_DETAIL` 均 9501；akshare 无对应函数 | 无真源 → 显式警示已加 |
| `st_changes` | `RPT_OPERATE_ST` 9501；akshare `stock_zh_a_st_em` 是**当前 ST 名单**（非变更历史），且走 push2 需绕代理 | 无直接历史源；**可由更名记录派生**（变更后简称含 ST/*ST）→ 方案待裁决 |
| `company_name_changes` | **已验证真源**：`ak.stock_info_sz_change_name("简称变更")` 7482 行（变更日期/证券代码/变更前后简称，最新 2026-09-23）；`("全称变更")` 1762 行（含变更前后全称） | 有真源；现实现走新浪逐股循环。**换源是行为变更（覆盖面变深市全量 vs 现逐股），待裁决** |

对照组 `RPT_LICO_FN_CPD` code=0 → 探测方法有效，9501 是报表确实不存在。

## 已落地（预授权分支）

- `DataSourceNotice` 组件：备查 Tab 两条（更名=partial / ST=unavailable）、三板 Tab、美股 Tab 各一条
- 全部 key、后端函数、数据流未动；技术债登记见下

## 技术债登记（方案 §8）

- `us_ipo` / `neeq_abnormal_trade` / `st_changes`：无公开 API 源，前端已显式标注「数据源未接入」；后续若接官方站（SEC EDGAR / neeq.com.cn / 交易所风险警示公告）需各自解析器
- `company_name_changes`：深交所真源已探明待接；换源同时可顺带派生 `st_changes`（一次抓取两个 feature）

## 落地记录（2026-09-28，Phase 13 批次 8）

- `get_company_name_changes`：新浪单股 demo → **深交所-名称变更真源**（`ak.stock_info_sz_change_name`，默认简称变更、param `symbol` 可选全称变更；日期窗口过滤 + 分页，按变更日期倒序）。覆盖范围仅深市证券，已在输出与前端 notice 注明。
- `get_st_changes`：占位提示 → **由深交所简称变更派生**（变更后含 ST 而变更前不含 → 实施ST；反之 → 撤销ST；双含 → 调整）。覆盖范围仅深市。
- 结构化 parser：`_parse_company_name_changes` / `_parse_st_changes` 注册进 FEATURE_TABLE（passthrough 26 → 7）。
- SCHEMA_VERSIONS 两项升 2.1；e2e 实测近 90 天更名 53 条（首页 50）、ST 派生 21 条（首条 2026-09-28 易联众 ST→撤销）。
- 前端备查 Tab 两条 DataSourceNotice 文案更新（均 partial，如实标注深市覆盖范围）。
- 测试：TestReferenceParse 3 个（含方向派生断言）；特征测试组 140 passed。
