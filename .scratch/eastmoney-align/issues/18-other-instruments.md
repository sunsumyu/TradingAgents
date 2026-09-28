# 18 — Phase 12.06 其它品种

**What to build:** 可转债列表、期权龙虎榜等。

**Blocked by:** None

**Status:** 可转债 done (2026-09-27)；期权龙虎榜未探测

- [x] 探测可转债报表：`RPT_BOND_CB_LIST` ✅（kzz 页源提取 + efinance 库互证）
- [x] 数据函数 + parser + 注册
- [x] 测试 + 前端面板 + 市场页注册
- [ ] 期权龙虎榜：未探测（后续照页源抓取法）


---

## 实施记录 (2026-09-27)

**探测：** `RPT_BOND_CB_LIST` ✅ 1059 只全量（data.eastmoney.com/kzz/ 页源提取，与 efinance 库互证）。
字段经三样例核验（新发 莱特转债/隆新转债 + 退市 普利退债）：规模=亿元、初始转股价=元、
新发最新价=面值100、`LISTING_DATE` 降序会把 null 排前（实测普利退债置顶）→ 默认按 `PUBLIC_START_DATE` 降序。

**后端：** `convert_bond.py`（get_convert_bond_list，排序白名单）+ `_parse_convert_bond_list`
+ `convert_bond_list` feature（TTL 3600）。feature 62 → 63。

**前端：** `ConvertBondPanel`（12 列）+ 市场页「转债」Tab。

**验证：** parser 套件 81 passed（新增 3）；parity/ttl/payload 全绿 97 passed；`tsc` 0；vitest 130；
e2e `convert_bond_list` → 50 items，首行 莱特转债(118077)/莱特光电/AA/5.25亿。
