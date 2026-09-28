# 13 — Phase 12.01 资金流引擎（行业/概念板块）

**What to build:** 个股/行业/概念主力净流入。行业与概念走东财 datacenter 报表（已实测核实）；个股排名走 push2 clist（生产通道，待本环境可核验后接入）。

**Blocked by:** None

**Status:** 行业/概念 done (2026-09-27)；个股排名 pending（push2 通道本环境不可核验）

- [x] 探测并核实数据源：`RPT_INDUSTRY_FUNDFLOW`（10.8 万行）/ `RPT_CONCEPT_FUNDFLOW`（400 概念）均 code=0，字段完整（四级单型+领涨股）
- [x] 数据函数 `fund_flow_ranking.get_board_fund_flow(board_type, curr_date, page_size)`（filter `TRADE_DATE<=` + 日期降序，取最新交易日整日数据，按主力净流入降序）
- [x] parser `_parse_board_fund_flow`（两个 key 共用）+ FEATURE_TABLE 注册 `industry_fund_flow` / `concept_fund_flow`（cache_ttl 3600）
- [x] 测试：5 个 parser 快照 + 注册/TTL 断言；实测 end-to-end（run_astock_feature → 50 items）
- [x] 前端 `FundFlowPanel`（行业/概念子页签，`FeatureDataTable` 渲染）+ 市场页「资金」Tab
- [ ] 个股资金流排名（push2 clist fid=f62）：本环境连对照组（涨幅榜）都取不到数据，字段语义无法核验；留待生产环境验证后接入

## 补充探测 (2026-09-28) —— 环境限制确证

push2 全系主机在本环境**网络层被阻断**（连接直接被远端关闭，非反爬 4xx）：
`push2.eastmoney.com` / `1.push2.` / `40.push2.` / `push2delay.` / `push2his.`
均同样失败，且 requests(trust_env=False) 与 curl_cffi chrome120 两通道一致——
排除代理与指纹因素。`fund_flow_ranking.py` 模块 docstring 的「本模块不含个股排名」
边界维持；接入代码本身仍是直读 JSON 的常规 clist 解析，待生产环境一次验证即可。
