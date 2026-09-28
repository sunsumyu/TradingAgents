# 16 — Phase 12.04 事件引擎

**What to build:** 股东大会、重大合同、关联交易等公司事件。

**Blocked by:** None

**Status:** 公司公告 + 事件分类树 done (2026-09-27 / 2026-09-28)；前端分类筛选 UI 待面板立项（API 能力已就绪）

- [x] 探测 np-anotice：`stock_list=<code>` 个股过滤 ✅（600519 三条全命中）；`codes=` 不过滤 ❌；f_node 一级分类 1-6 可用，二级树（股东大会/重大合同/关联交易）待后续探测
- [x] 数据函数 + parser + 注册（`stock_notices`，默认 TTL）
- [x] 测试 + 前端面板 + 个股 Tab 注册（公告，needsAStock）
- [x] 二级分类树探测 ✅（2026-09-28，见下）；分类过滤接入 `get_stock_notices(f_node, s_node)` + `_call_stock_notices` params 透传


---

## 实施记录 (2026-09-27)

**探测（实测）：** np-anotice `/api/security/ann` 带 `stock_list=<code>` 做个股过滤 ✅
（600519 三条全部命中）；`codes=` 参数不过滤 ❌（返回全市场最新）；f_node 一级分类 1-6
（权益分派/首发上市/交易异常/人事变动/经营类/投资类），二级分类树未探测。

**落地：** `stock_notices.py`（get_stock_notices，标题内 `|` 转义）+ `_parse_stock_notices`
（公告日/分类/标题）+ FEATURE_TABLE `stock_notices`（64 个，默认 TTL——公告及时性强）
+ `StockNoticesPanel`（列表渲染，非表格——标题长）+ 个股 Tab 栏「公告」。

**验证：** parser 套件 100 passed（新增 3）；`tsc` 0；vitest 130；e2e 实测
`stock_notices(600519)` → 30 条，首条 2026-08-15 业绩说明会公告。

## 二级分类树探测 (2026-09-28，实测)

**方法：** 黑盒采样 (f_node, s_node) 组合不可靠（部分组合回落父级全量）——改抓
`data.eastmoney.com/notices/` 页面 HTML，官方树定义在 `#filter_f_node` /
`#filter_s_node` 过滤器元素中（index.js 只含过滤机制，不含标签）。

**官方树：**

| f_node | 含义 | f_node | 含义 |
|---|---|---|---|
| 0 | 全部 | 4 | 信息变更 |
| 1 | 财务报告 | 5 | 重大事项 |
| 2 | 融资公告 | 6 | 资产重组 |
| 3 | 风险提示 | 7 | 持股变动 |

s_node（与 f_node 组合）：0 全部 / 1 定期报告 / 2 新股发行 / 3 增发 / 4 配股 /
5 业绩预告 / 6 业绩快报 / 7 重大合同 / 8 投资相关 / 9 股权激励 / 10 要约收购 /
11 吸收合并 / 12 回购 / 13 利润分配。

**关键修正：** 原工单假设的「股东大会 / 关联交易」**不在东财公告树的过滤节点中**
（仅作为 column_name 标签出现）。重大合同 = (f5, s7) 可用。

**组合过滤 e2e（600519）：** f1s1 定期报告 5 条（半年报/一季报）✓；
f1s5 业绩预告 1 条（2017 年度预增）✓；f7s0 持股变动 5 条（控股股东增持）✓；
f5s7 重大合同 0 条、f2s3 增发 0 条（茅台确无此类公告，语义正确）。

**落地：** `get_stock_notices(ticker, page_size, f_node, s_node)`（空结果注明过滤条件）
+ `_call_stock_notices` 透传 params；e2e 经 FEATURE_TABLE 验证默认 30 条 /
f1s1 命中半年报。分类树全文登记于 `stock_notices.py` 模块 docstring。
