# 06 — 5 个 Phase 9 feature 结构化 parser

**What to build:** 为已有的 5 个 Phase 9 feature（大宗交易明细/行业/大盘统计、分红送转、业绩预告/快报、分析师评级、机构持股）补齐结构化解析器，使其返回统一 `{columns, rows, meta}` 而非 raw markdown。后端数据函数已存在（akshare 路径），本工单只做「解析 + 契约对齐」，不改数据获取逻辑。

**Blocked by:** 02 — 统一 feature payload 契约

**Status:** ✅ DONE (2026-09-28 核验) — 7 个 feature 全部结构化（FEATURE_TABLE 实测无 passthrough）：`_parse_block_trade_detail/_industry/_market_stat`、`_parse_dividend_bonus`、`_parse_earnings_forecast/_express`、`_parse_analyst_rating`、`_parse_institutional_hold`；快照测试在 `tests/test_astock_parsers.py`（BLOCK_*/DIVIDEND/... 夹具，套件 140 passed）；解析失败返回空 items 而非抛错（test_empty 覆盖）

- [x] `block_trade_detail` / `block_trade_industry` / `block_trade_market_stat` 返回结构化
- [x] `dividend_bonus` 返回结构化
- [x] `earnings_forecast` / `earnings_express` 返回结构化
- [x] `analyst_rating` 返回结构化
- [x] `institutional_hold` 返回结构化
- [x] 每个 parser 有快照测试（输入样本 → 期望字段），放入 `tests/test_astock_parsers.py`
- [x] 无法解析时回退 `kind: "raw"` 而非抛错（envelope 始终携带 raw_md；parser 空输入返回空集）
