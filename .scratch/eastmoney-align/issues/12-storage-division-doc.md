# 12 — 存储分工文档化（PG vs TDengine）

**What to build:** 现状是分钟线走 TDengine、其余缓存/归档走 PostgreSQL，但该分工未文档化，容易让后来者把日频报表数据塞进时序库。本工单记录现有分工并规定新引擎数据的落点。**只写文档与方案，不改存储逻辑**。

**Blocked by:** None — can start immediately.

**Status:** ✅ DONE (2026-09-28 核验) — 文档已存在于方案 §5.1「存储分工（记录现状 + 新规）」+ `CONTEXT.md` 术语表两处条目（存储分工定义 / 新引擎落点指向 §5.1）；仅文档任务，未改任何存储代码

- [x] 在方案文档补充「存储分工」小节：PG（缓存 + `data_history` 永久归档）负责低频报表数据；TDengine 负责分钟级时序
- [x] 规定：Phase 12 新增引擎（资金流/股东/公司行动/事件/预期）一律走 PG 缓存，不进 TDengine
- [x] 在 `CONTEXT.md` 术语表补「存储分工」条目
- [x] 不修改任何现有存储/迁移代码
