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
