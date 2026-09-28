"""Snapshot tests for Phase 5 astock_features parsers.

Each test feeds a realistic markdown sample (matching the format produced by
the backend data-fetching functions) into a parser and asserts the resulting
structured dict.  This catches both regressions from a_stock.py format changes
and parser logic bugs.
"""

import pytest
from tradingagents_api.astock_features import (
    FEATURE_TABLE,
    _passthrough_parser,
    _parse_chip_distribution,
    _parse_dragon_tiger,
    _parse_northbound,
    _parse_concept_blocks,
    _parse_profit_forecast,
    _parse_lockup_expiry,
    _parse_hot_stocks,
    _parse_financial_csv,
    _parse_industry_comparison,
    _parse_insider_transactions,
    _parse_block_trade_detail,
    _parse_block_trade_industry,
    _parse_block_trade_market_stat,
    _parse_dividend_bonus,
    _parse_earnings_forecast,
    _parse_earnings_express,
    _parse_analyst_rating,
    _parse_board_fund_flow,
    _parse_convert_bond_list,
    _parse_research_reports,
    _parse_cn_quantity,
    _parse_macro_cpi,
    _parse_margin_detail,
    _parse_margin_market_stat,
    _parse_macro_gdp,
    _parse_ipo_declaration,
    _parse_ipo_listing,
    _parse_macro_pmi,
    _parse_stock_notices,
    _parse_free_holders,
    _parse_buyback,
    _parse_holder_increase,
    _parse_pledge_industry,
    _parse_pledge_market,
    _parse_pledge_stock,
    _parse_holder_num,
    _parse_institutional_hold,
    _parse_fund_purchase,
    _parse_fund_announcement,
    _parse_fund_scale,
    _parse_fund_open_info,
    _parse_investment_calendar,
    _parse_seat_activity,
    _parse_stock_activity,
    _parse_industry_chain_categories,
    _parse_industry_chain_chains,
    _parse_industry_chain_overview,
    _parse_industry_list,
    _parse_industry_commodity,
    _parse_industry_data_overview,
    _parse_industry_detail,
    _parse_survey_interaction,
    _parse_market_statistics,
    _parse_futures_position,
    _parse_company_name_changes,
    _parse_st_changes,
    _parse_consensus_estimate,
    _parse_hk_ipo,
)

TICKER = "600519"
DATE = "2026-08-26"


# ── Fixture markdown samples ─────────────────────────────────────────────────

CHIP_MD = """\
# 筹码分布 | 600519 | 2026-08-26
当前价: 1302.80
筹码峰值价: 1285.00
平均成本: 1270.50
获利盘比例: 56.3%
     1200.00 |   1.2% | ██
     1220.00 |   2.5% | ████
     1240.00 |   4.1% | ██████
     1260.00 |   8.3% | ████████████
     1280.00 |  15.7% | ████████████████████████[ ◄ 峰值]
     1300.00 |  12.1% | ██████████████████
     1320.00 |   9.8% | ███████████████
     1340.00 |   6.2% | █████████
     1360.00 |   3.5% | █████
"""

DRAGON_MD = """\
# 龙虎榜数据 | 002172 | 2026-08-26 (近30日)

## 上榜记录 (2 次)
日期 | 原因 | 净买入(万) | 换手率
  2026-08-26 | 日换手率达到20%的前5只证券 | -2566 | 35.33%
  2026-08-20 | 日涨幅偏离值达到7%的前5只证券 | 12906 | 26.36%

## 最近上榜席位明细 (2026-08-26)

### 买入席位 TOP5
营业部 | 买入(万) | 卖出(万) | 净额(万)
  国新证券北京分公司 | 4015 | 0 | 4015
  机构专用 | 1843 | 3012 | -1169

### 卖出席位 TOP5
营业部 | 买入(万) | 卖出(万) | 净额(万)
  国泰海通三亚迎宾路 | 1 | 7545 | -7544
  机构专用 | 1470 | 1907 | -437

## 机构动向
  机构买入 3385 万 | 卖出 8805 万 | 净额 -5420 万
"""

NORTHBOUND_MD = """\
# 北向资金流向 (2026-08-26)

Close: HGT(沪股通)=-9.28亿 SGT(深股通)=379.75亿 Total=370.47亿

## 近20日历史
日期 | HGT | SGT
  2026-08-12: HGT=-5.12 SGT=120.35
  2026-08-13: HGT=-8.44 SGT=95.20
  2026-08-14: HGT=-3.21 SGT=150.80
"""

CONCEPT_MD = """\
# 概念板块 | 600519 | 2026-08-26

Concept tags: 白酒 / 贵州板块 / 央企改革

## 行业
  白酒(申万二级): +1.23%
  食品饮料(申万一级): +0.85%

## 概念
  央企改革: -0.12%
  白酒概念: +1.05%

## 地域
  贵州板块: +0.56%
"""

PROFIT_MD = """\
# 盈利预测 | 600519 | 2026-08-26
# Source: 同花顺一致预期

FY2026.0: EPS=67.88 (range 64.78~77.85), analysts=49
FY2027.0: EPS=71.83 (range 67.23~84.02), analysts=48

Current: price = 1302.8, PE(TTM) = 20.0
Forward PE (FY2026.0): 19.2x
PEG: 3.30
"""

LOCKUP_MD = """\
# 限售解禁日历 | 002172 | 2026-08-26

## 个股解禁记录 (共 3 批)
解禁时间 | 类型 | 解禁数量 | 占比
  2019-06-19 | 定增限售 | 5000000 | 0.0906
  2018-07-17 | 股权激励 | 10000000 | 0.1754
  2017-11-06 | 首发原始 | 2000000 | 0.0199

未来 90 天无待解禁。
"""

HOT_MD = """\
# Hot Stocks with Topic Attribution (2026-08-26)
# Total: 3

  600519 贵州茅台: +1.23% 换手0.5% 成交额150000 大单净量2.1 | 白酒+消费
  000858 五粮液: -0.5% 换手0.8% 成交额80000 大单净量1.5 | 白酒+国企改革
  002304 洋河股份: +0.8% 换手1.2% 成交额50000 大单净量0.9 | 白酒+消费升级
"""


# ── Tests ────────────────────────────────────────────────────────────────────

class TestPassthroughParser:
    def test_returns_empty_dict(self):
        result = _passthrough_parser("any markdown", TICKER, DATE, {})
        assert result == {}

    def test_ignores_all_args(self):
        result = _passthrough_parser("", "", "", {"key": "val"})
        assert result == {}


class TestChipDistribution:
    def test_parses_header_fields(self):
        result = _parse_chip_distribution(CHIP_MD, TICKER, DATE, {})
        assert result["current_price"] == pytest.approx(1302.80)
        assert result["peak_price"] == pytest.approx(1285.00)
        assert result["avg_cost"] == pytest.approx(1270.50)
        assert result["profit_ratio"] == pytest.approx(56.3)

    def test_parses_price_levels(self):
        result = _parse_chip_distribution(CHIP_MD, TICKER, DATE, {})
        levels = result["price_levels"]
        assert len(levels) == 9
        # Peak level marked
        peak = [l for l in levels if l.get("is_peak")]
        assert len(peak) == 1
        assert peak[0]["price"] == pytest.approx(1280.00)

    def test_empty_on_error_text(self):
        result = _parse_chip_distribution("筹码分布查询失败: timeout", TICKER, DATE, {})
        assert result["price_levels"] == []


class TestDragonTiger:
    def test_parses_appearances(self):
        result = _parse_dragon_tiger(DRAGON_MD, TICKER, DATE, {})
        apps = result["appearances"]
        assert len(apps) == 2
        assert apps[0]["date"] == "2026-08-26"
        assert apps[0]["net_buy_wan"] == pytest.approx(-2566)

    def test_parses_seats(self):
        result = _parse_dragon_tiger(DRAGON_MD, TICKER, DATE, {})
        assert len(result["buy_seats"]) == 2
        assert len(result["sell_seats"]) == 2
        # Institution detection
        inst_buys = [s for s in result["buy_seats"] if s["is_institution"]]
        assert len(inst_buys) == 1

    def test_parses_institution_flow(self):
        result = _parse_dragon_tiger(DRAGON_MD, TICKER, DATE, {})
        assert result["inst_buy_wan"] == pytest.approx(3385)
        assert result["inst_sell_wan"] == pytest.approx(8805)

    def test_empty_on_no_board_text(self):
        md = "近30日未上龙虎榜"
        result = _parse_dragon_tiger(md, TICKER, DATE, {})
        assert result["appearances"] == []


class TestNorthbound:
    def test_parses_daily_flow(self):
        result = _parse_northbound(NORTHBOUND_MD, TICKER, DATE, {})
        assert result["hgt_net_inflow"] == pytest.approx(-9.28)
        assert result["sgt_net_inflow"] == pytest.approx(379.75)

    def test_parses_history(self):
        result = _parse_northbound(NORTHBOUND_MD, TICKER, DATE, {})
        hist = result["history"]
        assert len(hist) == 3
        assert hist[0]["date"] == "2026-08-12"
        assert hist[0]["hgt"] == pytest.approx(-5.12)
        assert hist[0]["sgt"] == pytest.approx(120.35)


class TestConceptBlocks:
    def test_parses_concepts(self):
        result = _parse_concept_blocks(CONCEPT_MD, TICKER, DATE, {})
        assert result["concepts"] == ["白酒", "贵州板块", "央企改革"]

    def test_parses_blocks(self):
        result = _parse_concept_blocks(CONCEPT_MD, TICKER, DATE, {})
        blocks = result["blocks"]
        assert len(blocks) == 5
        baijiu = next(b for b in blocks if b["name"] == "白酒")
        assert baijiu["change_pct"] == pytest.approx(1.23)
        assert baijiu["category"] == "行业"
        assert baijiu["note"] == "申万二级"


class TestProfitForecast:
    def test_parses_years(self):
        result = _parse_profit_forecast(PROFIT_MD, TICKER, DATE, {})
        years = result["years"]
        assert len(years) == 2
        assert years[0]["year"] == "2026"
        assert years[0]["mean_eps"] == pytest.approx(67.88)
        assert years[0]["analysts"] == 49

    def test_parses_valuation(self):
        result = _parse_profit_forecast(PROFIT_MD, TICKER, DATE, {})
        assert result["current_price"] == pytest.approx(1302.8)
        assert result["pe_ttm"] == pytest.approx(20.0)
        assert result["forward_pe"] == pytest.approx(19.2)
        assert result["peg"] == pytest.approx(3.30)


class TestLockupExpiry:
    def test_parses_batches(self):
        result = _parse_lockup_expiry(LOCKUP_MD, TICKER, DATE, {})
        assert len(result["batches"]) == 3
        assert result["batches"][0]["date"] == "2019-06-19"
        assert result["batches"][0]["shares_type"] == "定增限售"
        assert result["batches"][0]["ratio"] == pytest.approx(0.0906)

    def test_no_future_lockup(self):
        result = _parse_lockup_expiry(LOCKUP_MD, TICKER, DATE, {})
        assert result["has_future"] is False
        assert len(result["future_batches"]) == 0

    def test_with_future_lockup(self):
        md = LOCKUP_MD.replace(
            "未来 90 天无待解禁。",
            "未来 90 天待解禁：\n解禁时间 | 类型 | 解禁数量 | 占比\n  2026-09-15 | 股权激励 | 3000000 | 0.05",
        )
        result = _parse_lockup_expiry(md, TICKER, DATE, {})
        assert result["has_future"] is True
        assert len(result["future_batches"]) == 1
        assert result["future_batches"][0]["date"] == "2026-09-15"


class TestHotStocks:
    def test_parses_items(self):
        result = _parse_hot_stocks(HOT_MD, TICKER, DATE, {})
        items = result["items"]
        assert len(items) == 3
        assert items[0]["ticker"] == "600519"
        assert items[0]["name"] == "贵州茅台"
        assert items[0]["change_pct"] == pytest.approx(1.23)
        assert items[0]["turnover_rate"] == pytest.approx(0.5)
        assert items[0]["volume_wan"] == pytest.approx(150000)
        assert items[0]["net_flow_wan"] == pytest.approx(2.1)
        assert items[0]["topics"] == "白酒+消费"

    def test_total_from_header(self):
        result = _parse_hot_stocks(HOT_MD, TICKER, DATE, {})
        # Header says 3, but if not parsed, falls back to len(items)
        assert result["total"] >= 3

    def test_empty_on_no_data(self):
        result = _parse_hot_stocks("# Hot Stocks\n# 共 0 只", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


# ── Financial CSV fixtures ────────────────────────────────────────────────

BALANCE_SHEET_MD = """\
# Balance Sheet for 600519 (A-stock, quarterly)
# Data source: sina direct HTTP
# Data retrieved on: 2026-08-26 14:30:00
报告日,资产合计,负债合计,股东权益合计
2026-06-30,312456789.00,123456789.00,189000000.00
2026-03-31,305000000.00,120000000.00,185000000.00
2025-12-31,298000000.00,118000000.00,180000000.00
"""

INCOME_STATEMENT_MD = """\
# Income Statement for 600519 (A-stock, quarterly)
# Data source: sina direct HTTP
报告日,营业收入,营业成本,净利润
2026-06-30,789000000.00,234000000.00,356000000.00
2026-03-31,380000000.00,115000000.00,168000000.00
"""

CASHFLOW_MD = """\
# Cashflow for 600519 (A-stock, quarterly)
# Data source: sina direct HTTP
报告日,经营活动产生的现金流量净额,投资活动产生的现金流量净额,筹资活动产生的现金流量净额
2026-06-30,123000000.00,-45000000.00,-30000000.00
2026-03-31,56000000.00,-20000000.00,-15000000.00
2025-12-31,210000000.00,-80000000.00,-60000000.00
"""


# ── Tests ────────────────────────────────────────────────────────────────────

class TestParseFinancialCSV:
    def test_balance_sheet_structure(self):
        result = _parse_financial_csv(BALANCE_SHEET_MD, TICKER, DATE, {})
        assert result["periods"] == ["2026-06-30", "2026-03-31", "2025-12-31"]
        assert result["columns"] == ["资产合计", "负债合计", "股东权益合计"]

    def test_balance_sheet_values(self):
        result = _parse_financial_csv(BALANCE_SHEET_MD, TICKER, DATE, {})
        assert result["items"]["资产合计"][0] == pytest.approx(312456789.00)
        assert result["items"]["负债合计"][2] == pytest.approx(118000000.00)
        assert result["items"]["股东权益合计"][1] == pytest.approx(185000000.00)

    def test_income_statement(self):
        result = _parse_financial_csv(INCOME_STATEMENT_MD, TICKER, DATE, {})
        assert len(result["periods"]) == 2
        assert "营业收入" in result["columns"]
        assert result["items"]["净利润"][0] == pytest.approx(356000000.00)

    def test_cashflow(self):
        result = _parse_financial_csv(CASHFLOW_MD, TICKER, DATE, {})
        assert len(result["periods"]) == 3
        assert result["items"]["经营活动产生的现金流量净额"][0] == pytest.approx(123000000.00)
        assert result["items"]["投资活动产生的现金流量净额"][0] == pytest.approx(-45000000.00)

    def test_empty_string(self):
        result = _parse_financial_csv("", TICKER, DATE, {})
        assert result == {"periods": [], "columns": [], "items": {}}

    def test_no_report_date_column(self):
        md = "col1,col2\n1,2\n"
        result = _parse_financial_csv(md, TICKER, DATE, {})
        assert result == {"periods": [], "columns": [], "items": {}}

    def test_comments_skipped(self):
        result = _parse_financial_csv(BALANCE_SHEET_MD, TICKER, DATE, {})
        # Should not include comment lines in periods
        assert all(p.startswith("20") for p in result["periods"])


# ── Industry comparison fixtures ──────────────────────────────────────────

INDUSTRY_MD = """\
# 行业横向对比 | 600519 | 2026-08-26
## 全行业表现 (东财 5 个行业)
排名 | 行业 | 涨跌幅 | 上涨 | 下跌 | 领涨股
  1. 白酒 | +2.35% | 12 | 3 | 贵州茅台
  2. 食品饮料 | +1.20% | 18 | 5 | 伊利股份
  3. 银行 | +0.50% | 20 | 8 | 招商银行
  4. 房地产 | -0.80% | 5 | 25 | 万科A
  5. 煤炭 | -1.50% | 2 | 30 | 中国神华
"""


# ── Insider transactions fixtures ─────────────────────────────────────────

INSIDER_MD = """\
# Shareholder Research for 600519 (A-stock)
# Note: A-stock equivalent of insider transactions
# Data source: mootdx F10
# Data retrieved on: 2026-08-26 14:30:00

【1.股东结构】
截止日期: 2026-06-30
股东人数: 75000
人均持股: 2150股

【2.十大流通股东】
贵州茅台集团 | 61.99% | 国有
香港中央结算 | 7.23% | 外资

【4.股东变化】
2026-06-30 增持 机构专用 50万股
2026-03-31 减持 香港中央结算 20万股
"""


# ── Tests ────────────────────────────────────────────────────────────────────

class TestParseIndustryComparison:
    def test_parses_rankings(self):
        result = _parse_industry_comparison(INDUSTRY_MD, TICKER, DATE, {})
        rankings = result["rankings"]
        assert len(rankings) == 5

    def test_first_ranking(self):
        result = _parse_industry_comparison(INDUSTRY_MD, TICKER, DATE, {})
        first = result["rankings"][0]
        assert first["rank"] == 1
        assert first["name"] == "白酒"
        assert first["change_pct"] == pytest.approx(2.35)
        assert first["up_count"] == 12
        assert first["down_count"] == 3
        assert first["leader"] == "贵州茅台"

    def test_negative_change(self):
        result = _parse_industry_comparison(INDUSTRY_MD, TICKER, DATE, {})
        coal = next(r for r in result["rankings"] if r["name"] == "煤炭")
        assert coal["change_pct"] == pytest.approx(-1.50)

    def test_empty(self):
        result = _parse_industry_comparison("", TICKER, DATE, {})
        assert result["rankings"] == []

    def test_no_match_lines(self):
        result = _parse_industry_comparison("# header\nsome random text\n", TICKER, DATE, {})
        assert result["rankings"] == []


class TestParseInsiderTransactions:
    def test_parses_sections(self):
        result = _parse_insider_transactions(INSIDER_MD, TICKER, DATE, {})
        sections = result["sections"]
        assert len(sections) == 3
        titles = [s["title"] for s in sections]
        assert "1.股东结构" in titles
        assert "2.十大流通股东" in titles
        assert "4.股东变化" in titles

    def test_section_content_not_empty(self):
        result = _parse_insider_transactions(INSIDER_MD, TICKER, DATE, {})
        for s in result["sections"]:
            assert len(s["content"]) > 0

    def test_raw_text_preserved(self):
        result = _parse_insider_transactions(INSIDER_MD, TICKER, DATE, {})
        assert "Shareholder Research" in result["raw_text"]

    def test_empty(self):
        result = _parse_insider_transactions("", TICKER, DATE, {})
        assert result["sections"] == []
        assert result["raw_text"] == ""

    def test_no_sections_text(self):
        result = _parse_insider_transactions("just plain text\nno sections\n", TICKER, DATE, {})
        assert result["sections"] == []
        assert "plain text" in result["raw_text"]


# ── Phase 9 fixture markdown ─────────────────────────────────────────────────

BLOCK_DETAIL_MD = """\
# 个股大宗交易

日期: 2026-09-03

共 2 条记录
序号 | 证券代码 | 证券简称 | 成交价 | 收盘价 | 溢折价率(%) | 成交额(万) | 成交量(万) | 买方营业部 | 卖方营业部
  1 | 600519 | 贵州茅台 | 1850.00 | 1855.00 | -0.27 | 5000.00 | 27.03 | 中信证券北京 | 华泰证券上海
  2 | 000858 | 五粮液 | 145.50 | 146.00 | -0.34 | 3000.00 | 206.19 | 国泰君安深圳 | 招商证券广州
"""

BLOCK_INDUSTRY_MD = """\
# 大宗交易行业分布

统计月度: 2026-09

共 3 个行业
行业 | 溢折价率(%) | 成交金额(万) | 成交次数
  半导体 | -2.50 | 15000.00 | 12
  医药生物 | 1.20 | 8000.00 | 7
  食品饮料 | -0.80 | 12000.00 | 9
"""

BLOCK_MARKET_STAT_MD = """\
# 大盘大宗交易统计

统计月度: 2026-09

共 2 个交易日
日期 | 溢折价率(%) | 成交金额(万) | 成交次数
  2026-09-01 | -1.50 | 50000.00 | 45
  2026-09-02 | -0.80 | 48000.00 | 42
"""

DIVIDEND_MD = """\
# 增发送配

数据日期: 2026-09-04

共 2 条记录
序号 | 证券代码 | 证券简称 | 送股 | 转股 | 送转总数 | 派息(元) | 收益 | 净资产 | 公积金 | 未分配利润 | 预案公告日 | 股权登记日 | 除权除息日 | 方案进度
  1 | 600519 | 贵州茅台 | 0 | 0 | 0 | 23.882 | 12.50 | 15.20 | 2.10 | 8.50 | 2026-03-29 | 2026-06-15 | 2026-06-16 | 已实施
  2 | 000858 | 五粮液 | 0 | 0 | 0 | 10.50 | 5.80 | 9.30 | 1.50 | 6.20 | 2026-04-15 | 2026-07-10 | 2026-07-11 | 预案
"""

EARNINGS_FC_MD = """\
# 业绩预告

数据日期: 2026-09-30

共 2 条记录
序号 | 证券代码 | 证券简称 | 报告期 | 预告类型 | 预告内容 | 预告日期
  1 | 600519 | 贵州茅台 | 2026-09-30 | 业绩预增 | 预计净利润同比增长15%-20% | 2026-10-15
  2 | 000858 | 五粮液 | 2026-09-30 | 业绩预增 | 预计净利润同比增长10%-15% | 2026-10-12
"""

EARNINGS_EX_MD = """\
# 业绩快报

数据日期: 2026-09-30

共 1 条记录
序号 | 证券代码 | 证券简称 | 报告期 | 预告类型 | 预告内容 | 预告日期
  1 | 600519 | 贵州茅台 | 2026-09-30 | 业绩预增 | 预计净利润同比增长15%-20% | 2026-10-15
"""

ANALYST_MD = """\
# 价值分析 - 个股投资评级

数据日期: 2026-09-03
统计周期: 一月内

共 2 条记录
序号 | 报告日期 | 证券代码 | 证券简称 | 评级 | 评级变化 | 目标价 | EPS实际值 | T年度 | T+1年 | T+2年 | 标题 | 研究机构
  1 | 2026-09-02 | 600519 | 贵州茅台 | 买入 | 维持 | 2100.00 | 12.50 | 14.20 | 16.50 | 18.80 | 高端白酒龙头，业绩稳健增长 | 中信证券
  2 | 2026-09-01 | 000858 | 五粮液 | 增持 | 维持 | 180.00 | 5.80 | 6.50 | 7.30 | 8.10 | 浓香白酒龙头，渠道改革见效 | 国泰君安
"""

INST_HOLD_MD = """\
# 机构持股

数据日期: 2026-06-30

共 2 条记录
序号 | 证券代码 | 证券简称 | 所属行业 | 持股机构数 | 持仓数量(万股) | 持仓市值(万元) | 占总股本比例(%) | 占已流通A股比例(%) | 较上期增减(万股) | 仓位类型
  1 | 600519 | 贵州茅台 | 食品饮料 | 156 | 25000.00 | 4625000.00 | 19.90 | 20.50 | 500.00 | 增仓
  2 | 000858 | 五粮液 | 食品饮料 | 98 | 18000.00 | 2619000.00 | 14.65 | 15.20 | -200.00 | 减仓
"""


class TestParseBlockTradeDetail:
    def test_parses_rows(self):
        result = _parse_block_trade_detail(BLOCK_DETAIL_MD, TICKER, DATE, {})
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_first_row_fields(self):
        result = _parse_block_trade_detail(BLOCK_DETAIL_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["index"] == 1
        assert row["code"] == "600519"
        assert row["name"] == "贵州茅台"
        assert row["price"] == 1850.00
        assert row["close"] == 1855.00
        assert row["premium_pct"] == -0.27
        assert row["amount_wan"] == 5000.00
        assert row["volume_wan"] == 27.03
        assert row["buyer"] == "中信证券北京"
        assert row["seller"] == "华泰证券上海"

    def test_empty(self):
        result = _parse_block_trade_detail("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


class TestParseBlockTradeIndustry:
    def test_parses_rows(self):
        result = _parse_block_trade_industry(BLOCK_INDUSTRY_MD, TICKER, DATE, {})
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_first_row_fields(self):
        result = _parse_block_trade_industry(BLOCK_INDUSTRY_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["industry"] == "半导体"
        assert row["premium_pct"] == -2.50
        assert row["amount_wan"] == 15000.00
        assert row["count"] == 12

    def test_empty(self):
        result = _parse_block_trade_industry("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


class TestParseBlockTradeMarketStat:
    def test_parses_rows(self):
        result = _parse_block_trade_market_stat(BLOCK_MARKET_STAT_MD, TICKER, DATE, {})
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_first_row_fields(self):
        result = _parse_block_trade_market_stat(BLOCK_MARKET_STAT_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["date"] == "2026-09-01"
        assert row["premium_pct"] == -1.50
        assert row["amount_wan"] == 50000.00
        assert row["count"] == 45

    def test_empty(self):
        result = _parse_block_trade_market_stat("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


class TestParseDividendBonus:
    def test_parses_rows(self):
        result = _parse_dividend_bonus(DIVIDEND_MD, TICKER, DATE, {})
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_first_row_fields(self):
        result = _parse_dividend_bonus(DIVIDEND_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["index"] == 1
        assert row["code"] == "600519"
        assert row["name"] == "贵州茅台"
        assert row["bonus_share"] == 0
        assert row["transfer_share"] == 0
        assert row["total_share"] == 0
        assert row["dividend_yuan"] == 23.882
        assert row["eps"] == 12.50
        assert row["net_asset"] == 15.20
        assert row["reserve"] == 2.10
        assert row["retained"] == 8.50
        assert row["plan_date"] == "2026-03-29"
        assert row["record_date"] == "2026-06-15"
        assert row["ex_date"] == "2026-06-16"
        assert row["status"] == "已实施"

    def test_empty(self):
        result = _parse_dividend_bonus("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


class TestParseEarningsForecast:
    def test_parses_rows(self):
        result = _parse_earnings_forecast(EARNINGS_FC_MD, TICKER, DATE, {})
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_first_row_fields(self):
        result = _parse_earnings_forecast(EARNINGS_FC_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["index"] == 1
        assert row["code"] == "600519"
        assert row["name"] == "贵州茅台"
        assert row["report_period"] == "2026-09-30"
        assert row["forecast_type"] == "业绩预增"
        assert "净利润同比增长" in row["content"]
        assert row["forecast_date"] == "2026-10-15"

    def test_empty(self):
        result = _parse_earnings_forecast("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


class TestParseEarningsExpress:
    def test_parses_rows(self):
        result = _parse_earnings_express(EARNINGS_EX_MD, TICKER, DATE, {})
        assert result["total"] == 1
        assert len(result["items"]) == 1

    def test_first_row_fields(self):
        result = _parse_earnings_express(EARNINGS_EX_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["code"] == "600519"
        assert row["name"] == "贵州茅台"
        assert row["forecast_type"] == "业绩预增"

    def test_empty(self):
        result = _parse_earnings_express("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


class TestParseAnalystRating:
    def test_parses_rows(self):
        result = _parse_analyst_rating(ANALYST_MD, TICKER, DATE, {})
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_first_row_fields(self):
        result = _parse_analyst_rating(ANALYST_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["index"] == 1
        assert row["report_date"] == "2026-09-02"
        assert row["code"] == "600519"
        assert row["name"] == "贵州茅台"
        assert row["rating"] == "买入"
        assert row["rating_change"] == "维持"
        assert row["target_price"] == 2100.00
        assert row["eps_actual"] == 12.50
        assert row["eps_t"] == 14.20
        assert row["eps_t1"] == 16.50
        assert row["eps_t2"] == 18.80
        assert "高端白酒龙头" in row["title"]
        assert row["institution"] == "中信证券"

    def test_empty(self):
        result = _parse_analyst_rating("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


class TestParseInstitutionalHold:
    def test_parses_rows(self):
        result = _parse_institutional_hold(INST_HOLD_MD, TICKER, DATE, {})
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_first_row_fields(self):
        result = _parse_institutional_hold(INST_HOLD_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["index"] == 1
        assert row["code"] == "600519"
        assert row["name"] == "贵州茅台"
        assert row["industry"] == "食品饮料"
        assert row["inst_count"] == 156
        assert row["shares_wan"] == 25000.00
        assert row["market_value_wan"] == 4625000.00
        assert row["total_pct"] == 19.90
        assert row["float_pct"] == 20.50
        assert row["change_wan"] == 500.00
        assert row["position_type"] == "增仓"

    def test_empty(self):
        result = _parse_institutional_hold("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


FUND_FLOW_INDUSTRY_MD = """# 行业资金流 (主力净流入) | 2026-09-24
# Source: 东财 datacenter RPT_INDUSTRY_FUNDFLOW

板块 | 涨跌幅% | 主力净流入(亿) | 主力净占比% | 超大单(亿) | 大单(亿) | 中单(亿) | 小单(亿) | 领涨股
汽车零部件 | -0.64 | 9.90 | 2.23 | 5.43 | 4.47 | -0.69 | -9.74 | 均胜电子
军工电子Ⅱ | -0.74 | 7.50 | 3.85 | 7.07 | 0.42 | 0.60 | -8.11 | 雷科防务
"""

FUND_FLOW_CONCEPT_MD = """# 概念资金流 (主力净流入) | 2026-09-24
# Source: 东财 datacenter RPT_CONCEPT_FUNDFLOW

板块 | 涨跌幅% | 主力净流入(亿) | 主力净占比% | 超大单(亿) | 大单(亿) | 中单(亿) | 小单(亿) | 领涨股
大飞机 | -1.04 | 10.47 | 3.31 | 9.49 | 0.98 | -0.95 | -9.61 | 雷科防务
"""


class TestBoardFundFlowParse:
    """Phase 12.01 — 行业/概念板块资金流 parser（共用 _parse_board_fund_flow）。"""

    def test_industry_rows(self):
        result = _parse_board_fund_flow(FUND_FLOW_INDUSTRY_MD, TICKER, DATE, {})
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_first_row_fields(self):
        result = _parse_board_fund_flow(FUND_FLOW_INDUSTRY_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["board_name"] == "汽车零部件"
        assert row["change_pct"] == -0.64
        assert row["net_inflow_yi"] == 9.90
        assert row["net_inflow_pct"] == 2.23
        assert row["super_deal_yi"] == 5.43
        assert row["big_deal_yi"] == 4.47
        assert row["mid_deal_yi"] == -0.69
        assert row["small_deal_yi"] == -9.74
        assert row["lead_stock"] == "均胜电子"

    def test_concept_rows(self):
        result = _parse_board_fund_flow(FUND_FLOW_CONCEPT_MD, TICKER, DATE, {})
        assert result["total"] == 1
        assert result["items"][0]["board_name"] == "大飞机"
        assert result["items"][0]["lead_stock"] == "雷科防务"

    def test_registered_for_both_features(self):
        """两个 feature key 共用同一 parser，且都声明了当日 1h TTL。"""
        assert FEATURE_TABLE["industry_fund_flow"]["parse"] is _parse_board_fund_flow
        assert FEATURE_TABLE["concept_fund_flow"]["parse"] is _parse_board_fund_flow
        assert FEATURE_TABLE["industry_fund_flow"]["cache_ttl"] == 3600
        assert FEATURE_TABLE["concept_fund_flow"]["cache_ttl"] == 3600

    def test_empty(self):
        result = _parse_board_fund_flow("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


HOLDER_NUM_MD = """# 股东户数 | 600519
# Source: 东财 datacenter RPT_HOLDERNUMLATEST

报告期 | 股东户数 | 较上期增减 | 环比增幅% | 公告日期
2026-06-30 | 296,404 | 53,245 | 21.90 | 2026-08-15
2026-03-31 | 243,159 | -8,000 | -3.19 | 2026-04-22
"""

FREE_HOLDERS_MD = """# 十大流通股东 | 600519.SH | 2026-06-30
# Source: 东财 securities RPT_F10_EH_FREEHOLDERS

报告期 | 排名 | 股东名称 | 持股数量(万股) | 占流通股比%
2026-06-30 | 1 | 中国贵州茅台酒厂(集团)有限责任公司 | 68,128.29 | 54.50
2026-06-30 | 2 | 贵州省国有资本运营有限责任公司 | 5,699.68 | 4.56
"""

HOLDER_INCREASE_MD = """# 股东增减持 | 600519
# Source: 东财 datacenter RPT_SHARE_HOLDER_INCREASE

公告日 | 股东名称 | 方向 | 变动股数(万股) | 变动后持股比例%
2025-12-30 | 中国贵州茅台酒厂(集团)有限责任公司 | 增持 | 127.4234 | 54.40
2025-09-02 | 中国贵州茅台酒厂(集团)技术开发有限公司 | 增持 | 3.14 | 2.22
"""


class TestHolderStructureParse:
    """Phase 12.02 — 股东户数 / 十大流通股东 / 股东增减持 parser。"""

    def test_holder_num_rows(self):
        result = _parse_holder_num(HOLDER_NUM_MD, TICKER, DATE, {})
        assert result["total"] == 2
        row = result["items"][0]
        assert row["end_date"] == "2026-06-30"
        assert row["holder_num"] == 296404
        assert row["holder_num_change"] == 53245
        assert row["holder_num_ratio"] == 21.90
        assert row["hold_notice_date"] == "2026-08-15"

    def test_free_holders_rows(self):
        result = _parse_free_holders(FREE_HOLDERS_MD, TICKER, DATE, {})
        assert result["total"] == 2
        top = result["items"][0]
        assert top["holder_rank"] == 1
        assert "茅台酒厂(集团)" in top["holder_name"]
        assert top["hold_num_wan"] == 68128.29
        assert top["free_ratio"] == 54.50

    def test_holder_increase_rows(self):
        result = _parse_holder_increase(HOLDER_INCREASE_MD, TICKER, DATE, {})
        assert result["total"] == 2
        row = result["items"][0]
        assert row["direction"] == "增持"
        assert row["change_num_wan"] == 127.4234
        assert row["hold_ratio"] == 54.40

    def test_registered(self):
        assert FEATURE_TABLE["holder_num"]["parse"] is _parse_holder_num
        assert FEATURE_TABLE["free_holders"]["cache_ttl"] == 259200
        assert "cache_ttl" not in FEATURE_TABLE["holder_increase"]

    def test_empty(self):
        for parser in (_parse_holder_num, _parse_free_holders, _parse_holder_increase):
            result = parser("", TICKER, DATE, {})
            assert result["items"] == []
            assert result["total"] == 0


PLEDGE_MARKET_MD = """# 市场质押统计
# Source: 东财 datacenter RPT_CSDC_STATISTICS

日期 | 质押公司数 | 质押股数(亿股) | 质押市值(亿元) | 沪深300指数 | 沪深300涨跌幅%
2026-09-24 | 2,210 | 2,812.26 | 26,078.91 | 4,439.14 | -1.51
"""

PLEDGE_INDUSTRY_MD = """# 行业质押统计
# Source: 东财 datacenter RPT_CSDC_INDUSTRY_STATISTICS

行业 | 平均质押比例% | 质押市值(亿元) | 质押股数(亿股)
多元金融 | 18.14 | 371.27 | 75.20
医药商业 | 16.59 | 222.13 | 37.58
"""

PLEDGE_STOCK_MD = """# 个股质押
# Source: 东财 datacenter RPT_CSDC_LIST_NEWEST

日期 | 代码 | 简称 | 行业 | 质押比例% | 质押笔数 | 质押市值(亿元)
2026-09-24 | 600370 | *ST三房 | 化学纤维 | 78.74 | 34 | 46.56
2026-09-24 | 600519 | 贵州茅台 | 白酒Ⅱ | 0.06 | 10 | 9.36
"""

BUYBACK_MD = """# 股票回购
# Source: 东财 datacenter RPTA_WEB_GPHG

公告日 | 代码 | 简称 | 回购金额(万元) | 回购数量(万股) | 回购最低价 | 回购最高价 | 市价 | 涨跌幅%
2026-09-24 | 300750 | 宁德时代 | 19,999.34 | 68.04 | 293.69 | 294.53 | 293.50 | -2.49
"""


class TestCorporateActionsParse:
    """Phase 12.03 — 质押（市场/行业/个股）+ 回购 parser。"""

    def test_pledge_market(self):
        result = _parse_pledge_market(PLEDGE_MARKET_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["trade_date"] == "2026-09-24"
        assert row["pledge_co_num"] == 2210
        assert row["pledged_shares_yi"] == 2812.26
        assert row["pledge_mv_yi"] == 26078.91

    def test_pledge_industry(self):
        result = _parse_pledge_industry(PLEDGE_INDUSTRY_MD, TICKER, DATE, {})
        assert result["total"] == 2
        assert result["items"][0]["industry"] == "多元金融"
        assert result["items"][0]["avg_pledge_ratio"] == 18.14

    def test_pledge_stock(self):
        result = _parse_pledge_stock(PLEDGE_STOCK_MD, TICKER, DATE, {})
        assert result["total"] == 2
        assert result["items"][0]["pledge_ratio"] == 78.74
        assert result["items"][1]["name"] == "贵州茅台"

    def test_buyback(self):
        result = _parse_buyback(BUYBACK_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["code"] == "300750"
        assert row["amount_wan"] == 19999.34
        assert row["shares_wan"] == 68.04
        assert row["price_low"] == 293.69

    def test_registered(self):
        assert FEATURE_TABLE["pledge_market"]["cache_ttl"] == 86400
        assert FEATURE_TABLE["pledge_industry"]["cache_ttl"] == 86400
        assert FEATURE_TABLE["pledge_stock"]["cache_ttl"] == 86400
        assert "cache_ttl" not in FEATURE_TABLE["buyback"]

    def test_empty(self):
        for parser in (_parse_pledge_market, _parse_pledge_industry, _parse_pledge_stock, _parse_buyback):
            result = parser("", TICKER, DATE, {})
            assert result["items"] == []
            assert result["total"] == 0


CONVERT_BOND_MD = """# 可转债列表
# Source: 东财 datacenter RPT_BOND_CB_LIST

转债代码 | 转债简称 | 市场 | 正股代码 | 正股简称 | 评级 | 规模(亿元) | 转股价 | 最新价 | 申购日 | 上市日 | 到期日
118077 | 莱特转债 | 沪 | 688150 | 莱特光电 | AA | 5.25 | 44.82 | 100.00 | 2026-09-29 | - | 2032-09-29
123288 | 隆新转债 | 深 | 301149 | 隆华新材 | AA | 9.60 | 9.16 | 100.00 | 2026-09-29 | - | 2032-09-29
"""


class TestConvertBondParse:
    """Phase 12.06 — 可转债列表 parser（RPT_BOND_CB_LIST）。"""

    def test_rows(self):
        result = _parse_convert_bond_list(CONVERT_BOND_MD, TICKER, DATE, {})
        assert result["total"] == 2
        row = result["items"][0]
        assert row["bond_code"] == "118077"
        assert row["bond_name"] == "莱特转债"
        assert row["market"] == "沪"
        assert row["stock_code"] == "688150"
        assert row["stock_name"] == "莱特光电"
        assert row["rating"] == "AA"
        assert row["issue_scale_yi"] == 5.25
        assert row["convert_price"] == 44.82
        assert row["bond_price"] == 100.00
        assert row["public_start_date"] == "2026-09-29"
        assert row["listing_date"] == "-"  # 未上市以 - 占位（_cell 不做数值归一）
        assert row["expire_date"] == "2032-09-29"

    def test_registered(self):
        assert FEATURE_TABLE["convert_bond_list"]["parse"] is _parse_convert_bond_list
        assert FEATURE_TABLE["convert_bond_list"]["cache_ttl"] == 3600

    def test_empty(self):
        result = _parse_convert_bond_list("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


STOCK_NOTICES_MD = """# 公司公告 | 600519
# Source: 东财 np-anotice（个股公告）

公告日 | 分类 | 标题
2026-08-15 | 其他 | 贵州茅台:贵州茅台关于召开2026年半年度业绩说明会的公告
2026-08-15 | 半年度报告摘要 | 贵州茅台:贵州茅台2026年半年度报告摘要
"""


class TestStockNoticesParse:
    """Phase 12.04 — 公司公告 parser（np-anotice 个股公告流）。"""

    def test_rows(self):
        result = _parse_stock_notices(STOCK_NOTICES_MD, TICKER, DATE, {})
        assert result["total"] == 2
        row = result["items"][0]
        assert row["notice_date"] == "2026-08-15"
        assert row["column_name"] == "其他"
        assert "业绩说明会" in row["title"]

    def test_registered_default_ttl(self):
        entry = FEATURE_TABLE["stock_notices"]
        assert entry["parse"] is _parse_stock_notices
        assert "cache_ttl" not in entry  # 公告及时性强，走默认 4h/24h

    def test_empty(self):
        result = _parse_stock_notices("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


RESEARCH_REPORTS_MD = """# 研报流 | 600519 | 2026-03-31 ~ 2026-09-27
# Source: 东财 reportapi（研究报告）

研报日期 | 券商 | 评级 | 分析师 | 标题
2026-09-21 | 诚通证券 | 买入 | 陈文倩 | 贵州茅台公司跟踪报告：以动销定投放
"""

RESEARCH_REPORTS_MKT_MD = """# 研报流 | 全市场 | 2026-03-31 ~ 2026-09-27
# Source: 东财 reportapi（研究报告）

研报日期 | 券商 | 评级 | 分析师 | 正股代码 | 正股简称 | 标题
2026-09-27 | 华鑫证券 | 买入 | 张涵 | 605117 | 德业股份 | 公司动态研究报告
"""


class TestResearchReportsParse:
    """Phase 12.05 — 研报流 parser（个股 5 列 / 全市场 7 列双模式）。"""

    def test_per_stock_rows(self):
        result = _parse_research_reports(RESEARCH_REPORTS_MD, TICKER, DATE, {})
        assert result["total"] == 1
        row = result["items"][0]
        assert row["publish_date"] == "2026-09-21"
        assert row["org_name"] == "诚通证券"
        assert row["rating"] == "买入"
        assert row["researcher"] == "陈文倩"
        assert "以动销定投放" in row["title"]
        assert "stock_code" not in row  # 个股模式无正股列

    def test_market_rows(self):
        result = _parse_research_reports(RESEARCH_REPORTS_MKT_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["stock_code"] == "605117"
        assert row["stock_name"] == "德业股份"
        assert row["org_name"] == "华鑫证券"

    def test_registered_default_ttl(self):
        entry = FEATURE_TABLE["research_reports"]
        assert entry["parse"] is _parse_research_reports
        assert "cache_ttl" not in entry  # 券商观点按日发布，默认 4h/24h

    def test_empty(self):
        result = _parse_research_reports("", TICKER, DATE, {})
        assert result["items"] == []
        assert result["total"] == 0


MACRO_GDP_MD = """# 国内生产总值(GDP)

| 季度 | GDP(亿元) | 第一产业 | 第二产业 | 第三产业 |
|-----|---------|---------|--------|
| 2026年第1-2季度 | 695704 | 31522 | 250473 | 413709 |
| 2026年第1季度 | 334193 | 11941 | 116135 | 206117 |

## GDP同比增长

| 季度 | 同比增长% |
|-----|---------|
| 2026年第1-2季度 | 5.2 |

## 产业结构占比

| 季度 | 第一产业% | 第二产业% | 第三产业% |
|-----|---------|---------|---------|
| 2026年第1-2季度 | 4.53 | 36.00 | 59.47 |
"""

MACRO_CPI_MD = """# 消费者物价指数(CPI)

## 月度CPI

- {'商品': '中国CPI月率报告', '日期': '1996-02-01', '今值': 2.1}
- {'商品': '中国CPI月率报告', '日期': '1996-03-01', '今值': 2.3, '前值': 2.1}
"""

MACRO_PMI_MD = """# 采购经理人指数(PMI)

- {'季度': '2026年第2季度', '企业景气指数-指数': 109.5, '企业景气指数-同比': 9.5, '企业景气指数-环比': 0.2}
"""


class TestMacroParse:
    """Phase 13 批次 — 宏观数据三件套 parser（GDP 三表合并 / CPI / PMI dict 行）。"""

    def test_gdp_nested_panel_shape(self):
        """三表 → MacroAnalysisPanel 消费的转置形状 {gdp: {trend, growth, structure}}。"""
        result = _parse_macro_gdp(MACRO_GDP_MD, TICKER, DATE, {})
        gdp = result["gdp"]
        assert len(gdp["trend"]) == 2
        assert gdp["trend"][0]["quarter"] == "2026年第1-2季度"
        assert gdp["trend"][0]["gdp"] == 695704
        assert gdp["trend"][1]["gdp"] == 334193
        # 增长表只覆盖一期
        assert len(gdp["growth"]) == 1
        assert gdp["growth"][0]["gdp_growth"] == 5.2
        assert gdp["structure"][0]["primary_pct"] == 4.53
        assert gdp["structure"][0]["tertiary_pct"] == 59.47

    def test_cpi_dict_lines(self):
        result = _parse_macro_cpi(MACRO_CPI_MD, TICKER, DATE, {})
        assert result["total"] == 2
        assert result["items"][0]["date"] == "1996-02-01"
        assert result["items"][0]["value"] == 2.1
        assert result["items"][0]["prev"] is None  # 首行无前值
        assert result["items"][1]["prev"] == 2.1

    def test_pmi_dict_lines(self):
        result = _parse_macro_pmi(MACRO_PMI_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["quarter"] == "2026年第2季度"
        assert row["index"] == 109.5
        assert row["yoy"] == 9.5
        assert row["mom"] == 0.2

    def test_registered(self):
        for feat, parser in (
            ("macro_gdp", _parse_macro_gdp),
            ("macro_cpi", _parse_macro_cpi),
            ("macro_pmi", _parse_macro_pmi),
        ):
            assert FEATURE_TABLE[feat]["parse"] is parser

    def test_empty(self):
        assert _parse_macro_gdp("", TICKER, DATE, {}) == {}  # 空数据 → {}（前端回落 rawMd）
        for parser in (_parse_macro_cpi, _parse_macro_pmi):
            result = parser("", TICKER, DATE, {})
            assert result["items"] == []
            assert result["total"] == 0


IPO_DECLARATION_MD = """# 新股发行预告

序号 | 证券代码 | 证券简称 | 申购日期 | 申购代码 | 申购价(元) | 发行量(万) | 网上发行量(万) | 申购上限(万) | 市盈率(摊薄) | 中签号公布日
1 | 920157 | 宇特光电 | 2026-09-21 | 920157 | 13.75 | 1766.67 | 1236.67 | 61.83 | 14.99 | -
2 | 301660 | 粤芯半导体 | 2026-09-24 | 301660 | 12.01 | 51264.60 | 17942.40 | 12.80 | -- | 09-29
"""

IPO_LISTING_MD = """# 新股上市预告

序号 | 证券代码 | 证券简称 | 上市日期 | 发行价(元) | 发行量(万) | 网上发行量(万) | 市盈率(摊薄) | 申购日期 | 中签率%
1 | 301686 | 中塑股份 | 2026-09-22 | 55.28 | 1233.29 | 457.80 | 22.20 | 2026-09-10 | 1.3361
"""


class TestIpoParse:
    """Phase 13 批次 — 新股申报/上市 parser（IpoCenterPanel 契约）。"""

    def test_declaration_rows(self):
        result = _parse_ipo_declaration(IPO_DECLARATION_MD, TICKER, DATE, {})
        assert result["total"] == 2
        row = result["items"][0]
        assert row["code"] == "920157"
        assert row["name"] == "宇特光电"
        assert row["subscribe_date"] == "2026-09-21"
        assert row["price"] == 13.75
        assert row["volume_wan"] == 1766.67
        assert row["subscribe_limit_wan"] == 61.83
        assert row["pe_ratio"] == 14.99
        assert row["lottery_date"] == "-"

    def test_declaration_handles_missing_pe(self):
        # "--" 市盈率 → None
        row = _parse_ipo_declaration(IPO_DECLARATION_MD, TICKER, DATE, {})["items"][1]
        assert row["pe_ratio"] is None
        assert row["lottery_date"] == "09-29"

    def test_listing_win_rate_as_fraction(self):
        result = _parse_ipo_listing(IPO_LISTING_MD, TICKER, DATE, {})
        row = result["items"][0]
        assert row["code"] == "301686"
        assert row["listing_date"] == "2026-09-22"
        assert row["pe_ratio"] == 22.20
        # 后端百分数 1.3361 → 小数 0.013361（面板 ×100 显示）
        assert abs(row["win_rate"] - 0.013361) < 1e-9

    def test_registered(self):
        assert FEATURE_TABLE["ipo_declaration"]["parse"] is _parse_ipo_declaration
        assert FEATURE_TABLE["ipo_listing"]["parse"] is _parse_ipo_listing

    def test_empty(self):
        for parser in (_parse_ipo_declaration, _parse_ipo_listing):
            result = parser("", TICKER, DATE, {})
            assert result["items"] == []
            assert result["total"] == 0


class TestFundParse:
    def test_purchase_preserves_panel_contract_and_source_rows(self):
        md = """# 基金发行列表
共 2 只基金
| 基金代码 | 基金简称 | 基金类型 | 最新净值 | 净值日期 | 申购状态 | 赎回状态 | 下一开放日 | 最低购买 | 日累计限额 | 手续费 |
|---|---|---|---|---|---|---|---|---|---|---|
| 000001 | 华夏成长 | 混合型 | 1.238 | 2026-09-25 | 开放申购 | 暂停赎回 | - | 10 | 10000 | 0.15% |
| 000002 | 华夏精选 | 股票型 | -- | - | 暂停申购 | 开放赎回 | 2026-10-01 | 100 | - | - |
"""
        result = _parse_fund_purchase(md, TICKER, DATE, {})
        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["code"] == "000001"
        assert result["items"][0]["next_open"] == "-"
        assert result["items"][0]["fee_rate"] == 0.15
        assert result["issuing"][0]["code"] == "000001"
        assert result["upcoming"][0]["code"] == "000002"

    def test_section_tables_retain_original_columns(self):
        md = """# 基金公告
## reports
| 基金代码 | 公告标题 | 公告日期 |
|---|---|---|
| 000001 | 2026年第一季度报告 | 2026-04-20 |
## dividends
| 基金代码 | 分红方案 |
|---|---|
| 000002 | 每10份派0.5元 |
"""
        result = _parse_fund_announcement(md, TICKER, DATE, {})
        assert result["reports"][0]["公告标题"] == "2026年第一季度报告"
        assert result["dividends"][0]["基金代码"] == "000002"
        assert result["total"] == 2

    def test_scale_and_open_info_rows(self):
        md = """# 基金数据
共 1 只
| 基金类型 | 基金数量 | 基金规模(亿元) |
|---|---|---|
| 股票型 | 123 | 456.78 |
"""
        scale = _parse_fund_scale(md, TICKER, DATE, {})
        opened = _parse_fund_open_info(md, TICKER, DATE, {})
        assert scale["by_type"][0]["基金规模(亿元)"] == "456.78"
        assert opened["total"] == 1
        assert opened["items"] == scale["items"]

    def test_empty_and_registration(self):
        for feature, parser in (
            ("fund_purchase", _parse_fund_purchase),
            ("fund_announcement", _parse_fund_announcement),
            ("fund_scale", _parse_fund_scale),
            ("fund_open_info", _parse_fund_open_info),
        ):
            assert FEATURE_TABLE[feature]["parse"] is parser
            assert parser("暂无基金数据", TICKER, DATE, {})["total"] == 0


class TestCalendarAndActivityParse:
    def test_calendar_groups_all_five_event_types(self):
        md = """# 投资日历 | 2026-09-27

首发新股上市（共 1 条记录）
证券代码 | 证券简称 | 说明
  301688 | 电科思仪 | 首发新股上市日，发行价格12.00元/股

沪深停复牌（共 1 条记录）
证券代码 | 证券简称 | 停牌时间 | 复牌时间 | 说明 | 原因
  600001 | 邯郸钢铁 | 2026-09-27 | 2026-09-30 | 停牌 | 重大资产重组

特别处理（共 1 条记录）
证券代码 | 证券简称 | 说明
  000001 | ST平安 | 实施退市风险警示

限售解禁（共 1 条记录）
证券代码 | 证券简称 | 解禁日期 | 解禁数量(万) | 占总股本% | 解禁原因
  600519 | 贵州茅台 | 2026-09-27 | 12345.67 | 1.23 | 首发原股东限售股份
"""
        result = _parse_investment_calendar(md, TICKER, DATE, {})
        assert result["date"] == "2026-09-27"
        assert result["ipo_listing"][0]["code"] == "301688"
        assert "首发新股上市日" in result["ipo_listing"][0]["description"]
        assert result["suspension_resumption"][0]["suspend_date"] == "2026-09-27"
        assert result["suspension_resumption"][0]["reason"] == "重大资产重组"
        assert result["special_treatment"][0]["name"] == "ST平安"
        assert result["lockup_expiry"][0]["quantity_wan"] == pytest.approx(12345.67)
        assert result["lockup_expiry"][0]["ratio_pct"] == 1.23

    def test_activity_rows_and_registration(self):
        seat_md = """# 席位活跃度分析

周期: 3个月

共 2 个营业部
序号 | 营业部名称 | 龙虎榜成交额(万) | 上榜次数 | 买入额(万) | 卖出额(万) | 净买入额(万)
  1 | 国新证券北京分公司 | 4015.0 | 2 | 4015.0 | 0.0 | 4015.0
"""
        stock_md = """# 股票活跃度分析

周期: 1个月
日期范围: 2026-08-28 ~ 2026-09-27

共 1 只股票
序号 | 证券代码 | 证券简称 | 最近上榜日 | 龙虎榜成交额(万) | 上榜次数
  1 | 002172 | 澳洋健康 | 2026-08-26 | 12906.0 | 3
"""
        seats = _parse_seat_activity(seat_md, TICKER, DATE, {})
        stocks = _parse_stock_activity(stock_md, TICKER, DATE, {})
        assert seats["period"] == "3个月"
        assert seats["items"][0]["turnover_wan"] == 4015.0
        assert seats["items"][0]["net_buy_wan"] == 4015.0
        assert stocks["items"][0]["last_appear_date"] == "2026-08-26"
        assert stocks["items"][0]["appear_count"] == 3
        assert FEATURE_TABLE["investment_calendar"]["parse"] is _parse_investment_calendar
        assert FEATURE_TABLE["seat_activity"]["parse"] is _parse_seat_activity
        assert FEATURE_TABLE["stock_activity"]["parse"] is _parse_stock_activity

    def test_empty_calendar_has_all_groups(self):
        result = _parse_investment_calendar("# 投资日历 | 2026-09-27\n\n2026-09-27 无特别市场事件。", TICKER, DATE, {})
        for key in ("ipo_listing", "ipo_declaration", "suspension_resumption", "special_treatment", "lockup_expiry"):
            assert result[key] == []


class TestIndustryParse:
    def test_chain_categories_tree(self):
        md = """# 产业链分类

## 化工
- 涤纶纤维
- 氟化工
## 有色
- 稀土
"""
        result = _parse_industry_chain_categories(md, TICKER, DATE, {})
        assert result["categories"]["化工"] == ["涤纶纤维", "氟化工"]
        assert result["count"] == 2
        assert result["total"] == 3

    def test_chain_cards_sections(self):
        md = """# 产业链卡片

## hot

- 光模块 (+1.23%)
- 无人驾驶 (-0.45%)
## all

- 半导体 (+0.00%)
"""
        result = _parse_industry_chain_chains(md, TICKER, DATE, {})
        assert result["hot"][0] == {"name": "光模块", "change_pct": 1.23, "has_data": True}
        assert result["hot"][1]["change_pct"] == -0.45
        assert result["all"][0]["name"] == "半导体"
        assert result["total"] == 3

    def test_overview_composes_both(self):
        md = """# 产业链平台

## 分类 (1 个大类)

### 化工
- 涤纶纤维

## hot

- 光模块 (+2.00%)
"""
        result = _parse_industry_chain_overview(md, TICKER, DATE, {})
        assert result["categories"]["categories"]["化工"] == ["涤纶纤维"]
        assert result["chains"]["hot"][0]["change_pct"] == 2.0

    def test_industry_list_rows_and_cap_unit(self):
        md = """# 行业板块列表
共 2 个行业
| 板块名称 | 涨跌幅 | 总市值 | 换手率 | 涨/跌 |
|---------|-------|-------|-------|-------|
| 半导体 | +2.35% | 12300亿 | 1.80% | 45/12 |
| 白酒 | -0.50% | 8000亿 | 0.90% | 3/20 |
"""
        result = _parse_industry_list(md, TICKER, DATE, {})
        assert result["total"] == 2
        row = result["industries"][0]
        assert row["name"] == "半导体"
        assert row["change_pct"] == 2.35
        assert row["total_market_cap"] == pytest.approx(12300e8)
        assert row["turnover_rate"] == 1.80
        assert row["up_count"] == 45 and row["down_count"] == 12

    def test_commodity_history(self):
        md = """# 商品价格
## WTI原油 (美元/桶)
价格: 83.53  涨跌: +1.30 (+1.58%)

| 日期 | 价格 | 涨跌 | 涨跌幅 |
|-----|-----|-----|-------|
| 2026-08-27 | 83.53 | +1.30 | +1.58% |
| 2026-08-26 | 82.23 | -0.13 | -0.16% |
"""
        result = _parse_industry_commodity(md, TICKER, DATE, {})
        c = result["commodities"][0]
        assert c["name"] == "WTI原油"
        assert c["unit"] == "美元/桶"
        assert c["price"] == 83.53
        assert c["change_pct"] == 1.58
        assert c["history"][1]["change"] == -0.13

    def test_data_overview_and_detail(self):
        overview_md = """# 行业数据

## 行业分类 (2)

- 能源
- 钢铁

## 商品价格
### WTI原油 (美元/桶)
价格: 83.53  涨跌: +1.30 (+1.58%)
"""
        overview = _parse_industry_data_overview(overview_md, TICKER, DATE, {})
        assert overview["list"]["categories"] == ["能源", "钢铁"]
        assert overview["commodity"]["commodities"][0]["name"] == "WTI原油"

        detail_md = """# 半导体 行业详情

## 成分股 (1)

- 688981 中芯国际

## 近期走势

- 2026-09-25 +2.35%
"""
        detail = _parse_industry_detail(detail_md, TICKER, DATE, {})
        assert detail["name"] == "半导体"
        assert detail["stocks"] == ["688981 中芯国际"]
        assert detail["history"] == ["2026-09-25 +2.35%"]

    def test_registration(self):
        for feature, parser in (
            ("industry_chain_categories", _parse_industry_chain_categories),
            ("industry_chain_chains", _parse_industry_chain_chains),
            ("industry_chain_overview", _parse_industry_chain_overview),
            ("industry_list", _parse_industry_list),
            ("industry_detail", _parse_industry_detail),
            ("industry_commodity", _parse_industry_commodity),
            ("industry_data_overview", _parse_industry_data_overview),
        ):
            assert FEATURE_TABLE[feature]["parse"] is parser


class TestSurveyStatsFuturesParse:
    def test_survey_rows(self):
        md = """# 调研互动 (机构调研统计) | 2026-09-26

序号 | 证券代码 | 证券简称 | 所属行业 | 最新调研日 | 近一月调研 | 近三月调研 | 近半年调研 | 近一月机构 | 近三月机构 | 近半年机构 | 最新价 | 涨跌幅%
  1 | 600159 | 大龙地产 | 房地产开发 | 2026-09-29 | 1 | 1 | 1 | 1 | 1 | 1 | 2.72 | -0.37
"""
        result = _parse_survey_interaction(md, TICKER, DATE, {})
        assert result["total"] == 1
        row = result["items"][0]
        assert row["code"] == "600159"
        assert row["last_survey_date"] == "2026-09-29"
        assert row["price"] == 2.72
        assert row["change_pct"] == -0.37

    def test_market_statistics_three_sections(self):
        md = """# 市场统计 | 2026-09-26

## 市场规模统计

交易所 | 上市股票数(只) | 上市公司数(个) | 市价总值(亿) | 流通市值(亿) | 流通股本(亿股) | 平均市盈率 | 科创板平均市盈率
  上交所 | 2,361 | 2,323 | 679,242.85 | 600,041.34 | 48,657.33 | 16.86 | 117.56

## 成交概况（品种分类）

市场 | 品种 | 数量 | 成交金额(亿)
  深交所 | 基金 | 1,059 | 1,035.57

## 投资者情况（中国结算月度）

月份 | 新增投资者(万) | 期末投资者总量(万) | A股账户(万) | 沪深总市值(亿) | 户均市值(万)
  2023-08 | 99.59 | 22,141.58 | 22,082.23 | 808,664.77 | 36.62
"""
        result = _parse_market_statistics(md, TICKER, DATE, {})
        assert result["scale"]["total"] == 1
        assert result["scale"]["items"][0]["market_cap_yi"] == 679242.85
        assert result["scale"]["items"][0]["pe_avg"] == 16.86
        assert result["turnover"]["items"][0] == {
            "market": "深交所", "variety": "基金", "count": 1059.0, "amount_yi": 1035.57,
        }
        assert result["investors"]["items"][0]["month"] == "2023-08"

    def test_futures_contracts_and_totals(self):
        md = """# 股指期货持仓龙虎榜 | 品种: IF | 2026-09-24

## 合约 IF2612

### 成交量龙虎榜

名次 | 会员简称 | 成交量 | 增减
  1 | 中信期货 | 22,092 | +6848
  本日合计 | — | 86,000 | +31855

### 多头持仓龙虎榜

名次 | 会员简称 | 多单持仓 | 增减
  1 | 中信期货 | 12,000 | +300

### 空头持仓龙虎榜

名次 | 会员简称 | 空单持仓 | 增减
  1 | 海通期货 | 9,000 | -120
"""
        result = _parse_futures_position(md, TICKER, DATE, {})
        assert result["variety"] == "IF"
        assert result["date"] == "2026-09-24"
        assert result["total"] == 1
        c = result["contracts"][0]
        assert c["symbol"] == "IF2612"
        assert c["volume"]["items"][0] == {"rank": 1.0, "member": "中信期货", "value": 22092.0, "change": 6848.0}
        assert c["volume"]["total"] == {"rank": None, "member": "本日合计", "value": 86000.0, "change": 31855.0}
        assert c["long"]["items"][0]["value"] == 12000.0
        assert c["short"]["items"][0]["change"] == -120.0

    def test_registration_and_empty(self):
        assert FEATURE_TABLE["survey_interaction"]["parse"] is _parse_survey_interaction
        assert FEATURE_TABLE["market_statistics"]["parse"] is _parse_market_statistics
        assert FEATURE_TABLE["futures_position"]["parse"] is _parse_futures_position
        for parser in (_parse_survey_interaction, _parse_futures_position):
            assert parser("", TICKER, DATE, {})["total"] == 0
        empty = _parse_market_statistics("", TICKER, DATE, {})
        assert empty["scale"]["items"] == [] and empty["turnover"]["items"] == []


class TestReferenceParse:
    """工单 09 — 深交所更名真源 + ST 派生 parser。"""

    def test_company_name_changes_rows_and_total(self):
        md = """# 备查资料 (公司更名) | 2026-06-30 ~ 2026-09-28

数据源: 深交所-名称变更（简称变更，仅覆盖深市证券）
共 53 条更名记录（第 1 页，每页 50 条）

序号 | 变更日期 | 证券代码 | 证券简称 | 变更前 | 变更后
  1 | 2026-09-28 | 300096 | 易联众 | ST易联众 | 易联众
  2 | 2026-09-11 | 301689 | 电科思仪 | N电科思仪 | C电科思仪
"""
        result = _parse_company_name_changes(md, TICKER, DATE, {})
        assert result["total"] == 53
        assert result["source_symbol"] == "简称变更"
        assert result["items"][0] == {
            "change_date": "2026-09-28", "code": "300096", "name": "易联众",
            "before": "ST易联众", "after": "易联众",
        }

    def test_st_changes_direction(self):
        md = """# 备查资料 (ST变更) | 2026-06-30 ~ 2026-09-28

数据源: 深交所-简称变更派生（实施/撤销ST，仅覆盖深市证券）
共 2 条ST变更记录（第 1 页，每页 50 条）

序号 | 变更日期 | 证券代码 | 证券简称 | 变更前简称 | 变更后简称 | 方向
  1 | 2026-09-28 | 300096 | 易联众 | ST易联众 | 易联众 | 撤销ST
  2 | 2026-07-01 | 000010 | 美生 | 美生 | ST美生 | 实施ST
"""
        result = _parse_st_changes(md, TICKER, DATE, {})
        assert result["total"] == 2
        assert result["items"][0]["direction"] == "撤销ST"
        assert result["items"][1]["direction"] == "实施ST"

    def test_registration_and_empty(self):
        assert FEATURE_TABLE["company_name_changes"]["parse"] is _parse_company_name_changes
        assert FEATURE_TABLE["st_changes"]["parse"] is _parse_st_changes
        assert _parse_company_name_changes("", TICKER, DATE, {})["items"] == []
        assert _parse_st_changes("", TICKER, DATE, {})["items"] == []


class TestConsensusParse:
    """工单 17 余项 — 机构一致预期（RPT_WEB_RESPREDICT）。"""

    def test_rows_and_marks(self):
        md = """# 机构一致预期 | 600519
# Source: 东财 datacenter RPT_WEB_RESPREDICT

证券代码 | 证券简称 | 评级机构数 | 买入 | 增持 | 中性 | 减持 | 卖出 | 目标价低(元) | 目标价高(元) | 年度1 | EPS1(元) | 年度2 | EPS2(元)
600519 | 贵州茅台 | 43 | 34 | 9 | 0 | 0 | 0 | - | - | 2025A | 65.85 | 2026E | 67.25
"""
        result = _parse_consensus_estimate(md, TICKER, DATE, {})
        assert result["total"] == 1
        row = result["items"][0]
        assert row["code"] == "600519"
        assert row["rating_org_num"] == 43
        assert row["rating_buy"] == 34
        assert row["rating_add"] == 9
        assert row["aim_price_min"] is None  # 空目标价 → None
        assert row["year1"] == "2025A"
        assert row["eps1"] == 65.85
        assert row["year2"] == "2026E"
        assert row["eps2"] == 67.25

    def test_registration_and_empty(self):
        assert FEATURE_TABLE["consensus_estimate"]["parse"] is _parse_consensus_estimate
        assert _parse_consensus_estimate("", TICKER, DATE, {})["items"] == []


class TestHkIpoParse:
    """工单 08 — 港股新股（aastocks 真源）。"""

    def test_both_sections_and_hk_codes(self):
        md = """# 港股新股（IPO） | 2026-09-29
# Source: 阿斯达克 aastocks 新股频道

## 招股中

代码 | 名称 | 行业 | 招股价 | 每手股数 | 入场费(港元) | 招股截止日 | 上市日期
01256 | 奕斯伟计算 | 电子元件 | 1.48-1.59 | 2000 | 3212.07 | 2026-10-06 | 2026-10-09

## 已上市（半新股）

上市日期 | 代码 | 名称 | 上市价 | 超额倍数
2026-09-22 | 09856 | 纳真科技 | 32.96 | 34.2
2026-09-21 | 06727 | 星环科技 | 49.00 | 72.9
"""
        result = _parse_hk_ipo(md, TICKER, DATE, {})
        assert result["total"] == 3
        sub = result["subscribing"][0]
        assert sub["code"] == "01256"
        assert sub["price_range"] == "1.48-1.59"
        assert sub["lot_size"] == 2000.0
        assert sub["entry_fee"] == 3212.07
        assert sub["deadline"] == "2026-10-06"
        listed = result["listed"][0]
        assert listed["code"] == "09856"
        assert listed["offer_price"] == 32.96
        # 票内验收：代码必须为 5 位港股码（0 开头），非 A 股 6 位码
        for it in result["items"]:
            assert len(it["code"]) == 5 and it["code"].startswith("0")

    def test_registration_and_empty(self):
        assert FEATURE_TABLE["hk_ipo"]["parse"] is _parse_hk_ipo
        assert _parse_hk_ipo("", TICKER, DATE, {})["total"] == 0


MARGIN_DETAIL_MD = """市场: 沪市
日期: 2026-09-27

共 2000 只标的，展示前 50
序号 | 证券代码 | 证券简称 | 融资余额(亿) | 融资买入(亿) | 融资偿还(亿) | 净买入(亿) | 融券余量 | 融券卖出 | 融券偿还 | 净卖出
1 | 601318 | 中国平安 | 358.36亿 | 2.36亿 | 2.64亿 | -0.28亿 | 594.48万 | 2.14万 | 0.65万 | 1.49万
2 | 600519 | 贵州茅台 | 172.26亿 | 2.88亿 | 2.54亿 | 0.33亿 | 20.90万 | 5.16万 | 0.30万 | 4.86万
"""

MARGIN_STAT_MD = """# 融资融券市场统计

市场: 全市场

近 30 个交易日
日期 | 融资余额(亿) | 融资买入(亿) | 融券余量 | 融券余量金额(亿) | 融资融券余额(亿)
2026-08-14 | 13549.98亿 | 1015.95亿 | 2,883,001,415 | 165.63亿 | 13715.61亿
"""


class TestMarginParse:
    """Phase 13 批次 — 融资融券 parser（MarginTradingPanel 契约，元/股量纲）。"""

    def test_detail_rows_and_units(self):
        result = _parse_margin_detail(MARGIN_DETAIL_MD, TICKER, DATE, {})
        assert result["total"] == 2000
        assert result["market"] == "沪市"
        row = result["items"][0]
        assert row["code"] == "601318"
        assert row["margin_balance"] == 358.36e8  # 亿 → 元
        assert row["net_buy"] == pytest.approx(-0.28e8)
        assert row["short_qty"] == 594.48e4  # 万 → 股

    def test_stat_rows_and_units(self):
        result = _parse_margin_market_stat(MARGIN_STAT_MD, TICKER, DATE, {})
        assert result["total"] == 1
        row = result["items"][0]
        assert row["date"] == "2026-08-14"
        assert row["margin_balance"] == 13549.98e8
        assert row["short_qty"] == 2883001415  # 逗号数字原值
        assert row["total_balance"] == 13715.61e8

    def test_registered(self):
        assert FEATURE_TABLE["margin_detail"]["parse"] is _parse_margin_detail
        assert FEATURE_TABLE["margin_market_stat"]["parse"] is _parse_margin_market_stat

    def test_quantity_parser(self):
        assert _parse_cn_quantity("358.36亿") == 358.36e8
        assert _parse_cn_quantity("594.48万") == 594.48e4
        assert _parse_cn_quantity("2,883,001,415") == 2883001415.0
        assert _parse_cn_quantity("-0.28亿") == pytest.approx(-0.28e8)
        assert _parse_cn_quantity("-") is None

    def test_empty(self):
        for parser in (_parse_margin_detail, _parse_margin_market_stat):
            result = parser("", TICKER, DATE, {})
            assert result["items"] == []
