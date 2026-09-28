# 15 — Phase 12.03 公司行动引擎

**What to build:** 股票回购、股权质押、商誉、增发配股。

**Blocked by:** None

**Status:** 质押+回购 done (2026-09-27)；商誉/增发无源已登记

- [x] 探测 reportName（详见下）
- [x] 数据函数 + parser + 注册（质押 3 key TTL 24h；回购默认 4h/24h）
- [x] 测试 + 前端面板 + 市场页注册（质押/回购）
- [ ] 商誉/增发：无可核实端点，维持登记（见探测记录）


---

## 探测与实施记录 (2026-09-27)

**探测方法升级：** 12 个猜测 reportName 全部 9501 → 改为**抓取 data.eastmoney.com 真实页面/JS 提取 RPT_* 名**
（该方法已固化，后续工单照用）。商誉（/syyw）与增发（/zengfa）页为 591 字节 SPA 壳，未获端点 → 登记。

**核实并落地：**
| 报表 | 内容 | count | 已核验单位 |
|---|---|---|---|
| `RPT_CSDC_STATISTICS` | 市场质押统计 | 641 期 | 股数=万股(→亿)、市值=万元(→亿)；PM_RATIO 口径不符→不展示 |
| `RPT_CSDC_INDUSTRY_STATISTICS` | 行业质押 | 128 行 | 平均质押比例% |
| `RPT_CSDC_LIST_NEWEST` | 个股质押最新 | 4216 只 | 质押比例%；REPURCHASE_* 余额口径不明→不展示 |
| `RPTA_WEB_GPHG` | 股票回购 | 3094 条 | row0 验算：HGSL 29万股 × 13.42元 ≈ HGJE 3,891,257元 → HGSL=股、HGJE=元；HGFS 方式编码不展示 |

**后端：** `corporate_actions.py`（get_pledge_market / get_pledge_industry / get_pledge_stock 双模式 / get_buyback）
+ 4 parser + 4 新 feature（`pledge_market`/`pledge_industry`/`pledge_stock` TTL 24h；`buyback` 默认）。feature 58 → 62。

**前端：** `PledgePanel`（市场/行业/个股子页签）+ `BuybackPanel`，市场页新增「质押」「回购」Tab。

**验证：** parser 套件 78 passed（新增 6）；parity/ttl 全绿；`tsc` 0；vitest 130；
e2e `pledge_market` → 2210 家 / 2812.26 亿股 / 26,078.91 亿元（2026-09-24 期）。
