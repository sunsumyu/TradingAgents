# 07 — 注册 5 个 Phase 9 面板（个股 Tab + 市场页 Tab）

**What to build:** 5 个 Phase 9 面板组件（BlockTrade/DividendBonus/EarningsForecast/AnalystRating/InstitutionalHold）已实现且 `FeatureRenderer` 已有分派分支，但未在 `ASTOCK_FEATURE_TABS` 注册，导致经个股 Tab 栏不可达。本工单把它们注册进个股 Tab 与市场全景页对应 Tab，使其在两端可见。**纯新增注册**，不改面板内部实现。

**Blocked by:** 06 — 5 个 Phase 9 feature 结构化 parser（先有结构化数据再注册，避免注册后只显示 rawMd）

**Status:** ✅ DONE (2026-09-28 核验) — 5 个 key 已在 `ASTOCK_FEATURE_TABS`（block_trade_detail/dividend_bonus/earnings_forecast/analyst_rating/institutional_hold，含 label 与 needsAStock）；`AstockFeatureTabs.FeatureRenderer` 有对应分派分支；市场页同 5 Tab 挂载同名面板；工单 01 对等性测试转绿；`tsc` 0 错误

- [x] 5 个 key 加入 `ASTOCK_FEATURE_TABS`，含正确 label 与 `needsAStock`
- [x] 市场全景页对应 Tab 由 markdown 回退改为这 5 个面板
- [x] 工单 01 的对等性测试转绿
- [x] 前端 `tsc` 0 错误；面板在个股页与市场页均可渲染
