# 08 — `hk_ipo` 数据错标修复

**What to build:** `hk_ipo` 当前调用 akshare 港股 IPO 函数，但**返回的是 A 股 IPO 数据**（函数内已自述「akshare 数据源限制」），属于「看起来有数据、实则错误」，比静态文本更危险。修复为真实港股 IPO 数据源；若短期内无可核实的真实源，**先只加显式错误警示，不改现有逻辑与数据**（等用户裁决）。

**Blocked by:** None — can start immediately. ⚠️ 修复方向待用户裁决

**Status:** ✅ DONE (2026-09-29，方案 B aastocks 真源已接) — 错标修复完成

- [x] 先核查是否存在可用的港股 IPO 数据源（东财 reportName / akshare 其他函数）
- [x] 若存在：改为真实源，并加测试断言返回非 A 股代码（TestHkIpoParse：5 位 0 开头港股码）
- [x] 若不存在：输出显式「数据源不可用」警示 + 前端标注（换源前的过渡态，2026-09-27）
- [x] 修复方案先经用户确认后再改逻辑（用户以「继续」逐轮授权）


---

## 探测记录 (2026-09-27，实测)

1. **akshare `stock_ipo_hk_ths()` 现场核实为错标**：返回 50 行，列即 A 股 IPO 列（申购代码/网上发行/顶格申购需配市值…），
   代码 301718/301569/920196 —— 30x 创业板、920 北交所，非港股代码。
2. **东财 datacenter-web 探测无港股 IPO 报表**：`RPT_HKIPO_DETAIL` / `RPT_HKIPO_APPLYLIST` / `RPT_HK_IPO` / `RPT_HKIPO`
   全部 `9501 报表配置不存在`（同批对照组 `RPT_LICO_FN_CPD` code=0 → 探测方法有效）。
   `data.eastmoney.com/xg/hk/` 页面为 SPA 壳，静态 HTML/JS 内未提取到 reportName。
3. akshare 无其他港股 IPO 函数（仅 hist_min_em / hot_rank / profit_forecast_et）。

## 已落地（预授权分支：显式警示）

- 前端 `components/market/DataSourceNotice.tsx`（新增）——「数据源有误」红色警示条
- `MarketOverviewPage.tsx` 港股 Tab 顶部常显：说明实测证据（返回 A 股代码段），声明下表不可作为港股参考
- 后端函数/key/数据流未动（等用户裁决后再换真源）

## 换真源的可选方案（待裁决后实施）

- A. 港交所披露易 (www.hkex.com.hk) IPO 页抓取（权威，需解析）
- B. 阿斯达克 aastocks 新股页（结构稳定，反爬未知）
- C. ~~继续定位东财港股新股页的真实 XHR 端点~~ → **已排除（2026-09-28）**

## 补充探测 (2026-09-28，实测) —— 方案 C 排除

1. `data.eastmoney.com/xg/hk/` 返回 **404**（页面已下线，meta refresh 跳东财主页）；
   `xg/hk/dxsyl.html` 同 404。
2. 存活主页 `data.eastmoney.com/xg/`（200，203KB）全量 15 个 JS bundle 扫描：
   reportName 仅 A 股 5 个（`RPTA_APP_IPOAPPLY` / `RPT_IPO_CALENDAR` /
   `RPT_IPO_INFOALLNEW` / `RPT_IPO_REVIEW` / `RPT_SEO_DETAIL`），无任何港股报表。
3. 依命名规律定向猜测 8 个 `RPT_HK_*` 报表名（RPT_HK_IPO_INFOALLNEW 等）全空/9501。

**结论：东财已下线港股新股数据页，datacenter 无对应报表——方案 C 关闭。**
真源只剩方案 A（港交所披露易）或 B（阿斯达克），均为新站抓取，待用户裁决。

## 换源落地 (2026-09-29) —— 方案 B（aastocks）

**探测：** aastocks 新股主页可达（200，215KB），页面含结构化 IPO 表；
新浪港股 IPO 页为 JS 壳（无可提取数据）；HKEX 页面 404。

**换源：** `get_hk_ipo`（`tdx_reference.py`）重写为 aastocks 抓取
（curl_cffi chrome120）：「正在招股」表（代码/名称/行业/招股价区间/每手/
入场费/截止日/上市日）+ 半新股「已上市」表（过滤 `@` 衍生权证行、
剥离「跌穿上市价」状态后缀）；日期归一 ISO。

**结构化：** `_parse_hk_ipo` 双分区（subscribing/listed，items 合集）注册，
passthrough 7 → 6；SCHEMA `hk_ipo` → 2.1 失效错标缓存。

**e2e：** 招股中 1 只（奕斯伟计算 01256，电子元件，招股价 1.48-1.59，
每手 2000，入场费 3212.07，截止 2026-10-06，上市 2026-10-09）+ 已上市 16 只
（纳真科技 09856 34.2 倍 / 星环科技 06727 / 优地机器人 03231…），
全部 5 位港股码（0 开头）。票内验收「断言非 A 股代码」以
`TestHkIpoParse` 落实（144 passed）。

**前端：** 港股 Tab `DataSourceNotice` 从 mislabel（红色数据有误警示）
改为 partial（来源说明：aastocks 概览、非完整招股书）。
