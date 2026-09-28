# 02 — 统一 feature payload 契约

**What to build:** 定义所有结构化 feature 的统一数据载荷契约，前后端各一份类型。后端每个 feature 返回 `{columns, rows, meta}`：`columns` 为列定义（`key/label/unit/format`），`rows` 为记录数组，`meta` 携带来源与时间。日期统一 ISO（`YYYY-MM-DD`），数值列显式带单位与格式化提示。这是「通用表渲染」与「TTL 分级」的共同前置。

**Blocked by:** None — can start immediately.

**Status:** ✅ DONE (2026-09-28 核验) — 后端 `tradingagents_api/feature_payload.py`（FeaturePayload/Column/Provenance + Unit/Format 枚举 + `validate_payload` 行列对齐校验 + `raw_payload` 降级构造）；前端 `types.ts` FeatureColumn/FeaturePayloadEnvelope + `formatFeatureCell`；`tests/test_feature_payload.py` 6 passed；`GenericDataTable`（工单 05）按此契约渲染

- [x] 定义载荷类型：`columns: {key, label, unit?, format?}[]`、`rows: Record<string,unknown>[]`、`meta: {source, as_of, ttl_hint?}`（实施时 meta 命名为 provenance，语义一致）
- [x] 前端建立对应 TS 类型；后端建立对应 Pydantic/字典约定
- [x] 保留 `kind: "raw"` 作为显式降级类型（承载尚未结构化的 markdown），并在方案技术债清单登记
- [x] 约定数值列的单位与格式枚举（元/万元/亿元/%/股/万股，Unit(str, Enum) 封闭词表）
- [x] 单元测试：契约校验函数（列定义完整性、rows 与 columns 对齐——`validate_payload` 报错带行号与未知键）
