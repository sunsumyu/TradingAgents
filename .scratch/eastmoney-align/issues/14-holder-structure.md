# 14 — Phase 12.02 持仓股东引擎

**What to build:** 股东户数、十大股东/十大流通股东、机构持仓汇总。

**Blocked by:** None

**Status:** ✅ done (2026-09-27 三 feature 全竖切；2026-09-28 股东户数历史期接入 → 工单全部完成)

- [x] 探测东财 reportName：股东户数（候选 `RPT_HOLDERNUMLATEST` — 方案文档称已验证）、十大股东（候选 `RPT_F10_EH_HOLDER`? 需实测）、股东增减持（`RPT_SHARE_HOLDER_INCREASE` 已验证）
- [x] 数据函数 + parser + FEATURE_TABLE 注册（季报类 cache_ttl 72h）
- [x] 测试（快照 + 注册断言）+ 前端面板（GenericDataTable）+ 市场页注册
- [x] 股东户数历史期报表：`RPT_HOLDERNUM_DET` 探测成功并换源（2026-09-28）


---

## 实施记录 (2026-09-27)

**探测（全部实测核实，茅台案例交叉验证）：**
- `RPT_HOLDERNUMLATEST`（datacenter-web）✅ 每股仅**最新一期**（实测 count=1；历史期需 `RPT_HOLDERNUMLIST` 类报表，待后续探测）
- `RPT_F10_EH_FREEHOLDERS`（securities F10 通路）✅ 十大流通股东，SECUCODE 过滤；茅台集团 68,128.29 万股 / 54.50%
- `RPT_SHARE_HOLDER_INCREASE`（datacenter-web）✅ 14.7 万行；单位用茅台案例锁定：`CHANGE_NUM_SYMBOL`=万股（带符号）、`HOLD_RATIO`=百分比（54.4 ↔ 十大流通 54.49% 一致）；`CHANGE_RATE`/`AFTER_CHANGE_RATE` 符号量纲行间不一致 → **不采用**（宁缺勿错）

**后端：**
- `holder_structure.py`：`get_holder_num` / `get_free_holders` / `get_holder_increase`（curl_cffi chrome120，两次退避重试，securities F10 独立 host）
- 3 个新 feature：`holder_num`(TTL 24h) / `free_holders`(TTL 72h 季报) / `holder_increase`(默认 4h/24h 事件类)
- 5 个 parser 测试（快照取自实测输出）

**前端：**
- `HolderPanel`（一个组件三形态 num/free/increase）+ 个股 Tab 栏新增 3 个 tab：股东户数 / 十大流通 / 增减持（needsAStock）
- feature key 55 → 58

**验证：** parser+ttl 79 passed；parity 3 passed；`tsc` 0 错误；vitest 130 passed；e2e `run_astock_feature(holder_num, 600519)` → 296,404 户 +21.90%（与探测一致）。

## 股东户数历史期接入 (2026-09-28)

- 探测：`RPT_HOLDERNUM_DET` ✅（600519 实测 30 期起可分页至 2015 年；字段含
  `AVG_HOLD_NUM` 户均持股数 / `AVG_MARKET_CAP` 户均市值 / `INTERVAL_CHRATE`
  区间涨跌幅 / `CLOSE_PRICE`，量纲自洽：4217 股 × 1185.49 元 ≈ 500 万户均市值）。
  原 docstring 猜测的 `RPT_HOLDERNUMLIST` 不存在（9501）。
- 换源：`get_holder_num` 报表名 → `RPT_HOLDERNUM_DET`，**markdown 5 列结构不变**
  （报告期|股东户数|较上期增减|环比增幅%|公告日期），`_parse_holder_num` 与
  `HolderPanel` 零改动；扩展字段已核验暂不展示（宁缺勿错）。
- 缓存：`holder_num` SCHEMA_VERSIONS → 2.2（首次 e2e 恰逢网络抖动把空结果
  缓存进 2.1，再升一级失效——与投资日历批次同一教训）。
- e2e：50 期（2026-06-30 → 2015-09-30），最新期 296,404 户 +21.9%；
  特征测试组 140 passed。
