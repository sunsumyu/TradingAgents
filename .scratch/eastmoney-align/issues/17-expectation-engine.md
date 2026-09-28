# 17 — Phase 12.05 预期引擎

**What to build:** 研报流（reportapi）、一致预期明细（`RPT_VALUEANALYSIS_DET`）。

**Blocked by:** None

**Status:** ✅ done (2026-09-27 研报流；2026-09-28 一致预期接入 → 工单全部完成。关键修正见下)

- [x] 重试 `RPT_VALUEANALYSIS_DET`：2026-09-27 三次（间隔约 1-2 小时）均 9701 服务器繁忙 —— 非瞬时抖动，疑需 Referer/不同 host 或已下线；下次带浏览器网络面板核实
- [x] 探测 reportapi.eastmoney.com/report/list ✅ 全市场 7197 条 + 个股 code= 过滤 40 条（茅台）
- [x] 数据函数 + parser + 注册（`research_reports`，默认 TTL）
- [x] 测试 + 前端面板 + 个股 Tab 注册（研报，needsAStock）
- [x] 一致预期明细 ✅（2026-09-28：真实报表为 `RPT_WEB_RESPREDICT`，非 RPT_VALUEANALYSIS_DET——见下）


---

## 实施记录 (2026-09-27)

**探测（实测）：** reportapi `/report/list` ✅（方案文档列为已验证开放端点）
- 全市场 qType=0 → total=7197，字段 title/orgSName/publishDate/emRatingName/researcher/stockName/stockCode
- 个股 `code=600519` → total=40（180 天窗口）；`beginTime/endTime` 必填（缺省报错）
- `RPT_VALUEANALYSIS_DET` 第三次 9701 —— 记录待核

**落地：** `research_reports.py`（get_research_reports，个股/全市场双模式，窗口默认 180 天，
日期窗口必填已处理）+ `_parse_research_reports`（个股 5 列 / 全市场 7 列自适应）
+ `research_reports` feature（65 个，默认 TTL——券商观点按日发布）
+ `ResearchReportsPanel`（列表渲染：日期 + 评级徽标涨跌色 + 券商·分析师 + 标题）
+ 个股 Tab 栏「研报」（needsAStock）。

**验证：** parser 套件 104 passed（新增 4）；`tsc` 0；vitest 130；
e2e 实测 `research_reports(600519)` → 30 条，首条 2026-09-21 诚通证券·买入·陈文倩
「贵州茅台公司跟踪报告：以动销定投放，缓解市场压力，低速稳态发展」。

## 一致预期接入 (2026-09-28) —— 报表名修正 + 落地

**关键修正：** 工单原假设的 `RPT_VALUEANALYSIS_DET`（9701 待核项）今日复探：
带个股过滤 `(SECURITY_CODE=...)` **可达**，但字段为 PE_TTM/PB_MRQ/PS_TTM/PEG/
市值——是**估值分析明细**而非一致预期，报表名定位本身错了。
真实的一致预期报表 = **`RPT_WEB_RESPREDICT`**（从 akshare
`stock_profit_forecast_em` 源码反查获得）：

* 必须用具名列组 `columns=WEB_RESPREDICT`（ALL → 9501）+ 排序 `RATING_ORG_NUM`；
  此前 9701×3 的根因即参数形态不符。
* 三种过滤均 code=0：无过滤（全市场 587 页）/ `INDUSTRY_BOARD`（半导体 29 页）/
  `SECURITY_CODE`（个股 1 条）。
* 字段：评级分布（买入/增持/中性/减持/卖出）+ 四年 EPS（YEAR_MARK A=实际/E=预测）
  + 目标价区间（DEC_AIMPRICE MIN/MAX）。

**落地：** 新模块 `consensus_estimate.py`（curl_cffi chrome120，两次退避）+
新 feature `consensus_estimate`（第 66 个 key，TTL 86400——评级共识随研报发布更新）
+ `_parse_consensus_estimate`（14 列，年度形如 2025A/2026E）+
`AstockFeatureKey` 联合类型补 key（个股/市场双模式：个股 1 条最新共识、
市场按机构数降序）。

**e2e：** 个股 600519 → 43 机构（34 买入+9 增持）、目标价 1430–2030 元、
2025A EPS 65.85 / 2026E 67.25；市场模式 Top3：茅台 43 / 东鹏 41 / 伊利 38。
特征测试组 142 passed。前端面板挂载（AnalystRatingPanel 汇总区）待面板立项。
