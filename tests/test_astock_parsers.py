"""Snapshot tests for Phase 5 astock_features parsers.

Each test feeds a realistic markdown sample (matching the format produced by
the backend data-fetching functions) into a parser and asserts the resulting
structured dict.  This catches both regressions from a_stock.py format changes
and parser logic bugs.
"""

import pytest
from tradingagents_api.astock_features import (
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
