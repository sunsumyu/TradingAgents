# 11 — 缓存 TTL 分级

**What to build:** 当前 `CacheManager` 只对 `ohlcv` 特判 TTL，其余数据一律 4h（盘中）/24h（盘后）；Phase 9 规格里写的按类型分级（机构持股 72h、分析师评级 6h 等）并未实现。让 `FEATURE_TABLE` 每条 feature 声明自己的 `cache_ttl`，由缓存层读取，使 TTL 策略从隐式变显式。⚠️ 是否实施待用户裁决。

**Blocked by:** 02 — 统一 feature payload 契约（`meta.ttl_hint` 与 TTL 分级共用契约）

**Status:** done (2026-09-27, 机制+声明已实施；改/撤任一 TTL 是一行改动)

- [x] `FEATURE_TABLE` 条目支持 `cache_ttl` 声明（缺省沿用现状默认，不影响未声明者）
- [x] `CacheManager` 按 feature 声明的 TTL 判过期（保留现有 `ohlcv` 特判兼容）
- [x] 为季报类（机构持股/十大股东）设长 TTL，为当日行情类设短 TTL
- [x] 单测：TTL 读取、过期判定、未声明时回退默认
- [x] 实施前先经用户确认


---

## 实施记录 (2026-09-27)

**机制（`tradingagents/cache/manager.py`，纯新增）：**
- `_FEATURE_TTL_OVERRIDES` 注册表 + `register_feature_ttl(feature, seconds)` + `feature_ttl(feature)`
- `_ttl_for_type()` 先查显式声明 → 未声明者完全沿用旧行为（ohlcv 24h 特判保留；其余交易日 4h / 盘后 24h）
- 非正值忽略（错误声明不可能关掉缓存）

**声明（`FEATURE_TABLE`，按 Phase 9 规格 §6）：**

| feature | cache_ttl | 依据 |
|---|---|---|
| block_trade_detail | 3600 (1h) | 当日行情 |
| block_trade_market_stat | 3600 (1h) | 当日行情 |
| block_trade_industry | 86400 (24h) | 月度数据 |
| dividend_bonus / earnings_forecast / earnings_express | 86400 (24h) | 显式化（与默认一致） |
| analyst_rating | 21600 (6h) | 规格 §6 |
| institutional_hold | 259200 (72h) | 规格 §6（季报数据变化慢） |

导入 `astock_features` 时把声明注册进缓存层；`tradingagents/cache/__init__.py` 导出新 API。

**测试：** `tests/test_feature_ttl.py` 7 个单测（声明优先、未声明回退、ohlcv 保留、非正值忽略、覆盖语义、FEATURE_TABLE 注册生效、Phase 9 数值对表）。78 passed（与 parser/payload/parity 套件合跑）。
