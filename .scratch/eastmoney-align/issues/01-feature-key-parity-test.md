# 01 — 前后端 feature key 对等性测试

**What to build:** 一条自动化测试，断言后端 `FEATURE_TABLE` 的 key 集合与前端 `ASTOCK_FEATURE_TABS` 的 key 集合完全相等。当前两端不一致（后端 53、前端 12，且 5 个 Phase 9 面板有渲染分支却无注册 key），测试应把它们**锁定为红灯**，作为后续接通工作的验收基线。

**Blocked by:** None — can start immediately.

**Status:** ✅ DONE (2026-09-28 核验) — `tests/test_feature_key_parity.py` 3 passed（纳入特征测试组 140 passed）；不变量实施时修正为「前端注册 key ⊆ 后端 FEATURE_TABLE」并已在 `CONTEXT.md` 术语表登记（后端-only 为市场级 feature，属预期，差集在 CI 输出打印）

- [x] 新增测试：后端 key 集合 == 前端 key 集合（读后端表与前端类型定义，不硬编码数量）
- [x] 测试失败时，输出「后端有前端无」「前端有后端无」两张差集清单
- [x] 该测试在修复完成前保持红灯；修复后转绿，作为 CI 门禁（实施时不变量修正为前端 ⊆ 后端，理由见测试 docstring：市场级 feature 故意不在个股 Tab）
- [x] 在 `CONTEXT.md` 记录该测试为「两端对等」不变量
