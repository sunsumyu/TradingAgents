"""Contract tests for the screener service migration (ticket #3).

The service keeps LLM parsing, candidate discovery, FEATURE_TABLE fetching,
and the legacy partial-match scoring formula — while ALL filter comparison
runs through the screener engine (the single evaluation authority).

LLM parsing and FEATURE_TABLE are stubbed; no network access.
"""

import pytest

from tradingagents_api import astock_features, screener as screener_service
from tradingagents_api.screener import (
    ScreenerCriteria,
    ScreenerFilter,
    run_screener,
    run_template_screener,
)
from tradingagents_api.screener import _parse_query_with_llm


# ── Stubs ────────────────────────────────────────────────────────────────────

UNIVERSE = [
    {"ticker": "600519", "name": "贵州茅台"},
    {"ticker": "000858", "name": "五粮液"},
    {"ticker": "601318", "name": "中国平安"},
]

STOCK_FEATURES = {
    "600519": {"pe": 25.0, "profit_ratio": 80.0, "industry": "白酒 消费"},
    "000858": {"pe": 15.0, "profit_ratio": None, "industry": "白酒 消费"},
    "601318": {"pe": 9.0, "profit_ratio": 30.0, "industry": "保险 金融"},
}


def _stub_feature_table():
    def _call_universe(ticker, today, params):
        return "stub"

    def _parse_universe(md, ticker, today, params):
        return {"items": [dict(u) for u in UNIVERSE]}

    def _call(ticker, today, params):
        return "stub"

    def _parse_profit(md, ticker, today, params):
        info = STOCK_FEATURES.get(ticker, {})
        return {"pe_ttm": info.get("pe")} if info.get("pe") is not None else {}

    def _parse_chip(md, ticker, today, params):
        info = STOCK_FEATURES.get(ticker, {})
        if info.get("profit_ratio") is None:
            return {}
        return {"profit_ratio": info["profit_ratio"]}

    def _parse_concept(md, ticker, today, params):
        info = STOCK_FEATURES.get(ticker, {})
        return {"concepts": (info.get("industry") or "").split(),
                "blocks": [{"name": n, "category": "行业"}
                           for n in (info.get("industry") or "").split()]}

    return {
        "hot_stocks": {"call": _call_universe, "parse": _parse_universe},
        "profit_forecast": {"call": _call, "parse": _parse_profit},
        "chip_distribution": {"call": _call, "parse": _parse_chip},
        "concept_blocks": {"call": _call, "parse": _parse_concept},
    }


@pytest.fixture()
def stubbed(monkeypatch):
    monkeypatch.setattr(astock_features, "FEATURE_TABLE", _stub_feature_table())
    return stubbed


def _force_criteria(monkeypatch, filters):
    monkeypatch.setattr(
        screener_service,
        "_parse_query_with_llm",
        lambda query, config: ScreenerCriteria(filters=filters),
    )


def _config():
    return {"llm_provider": "openai"}


# ── Tests ────────────────────────────────────────────────────────────────────


class TestEngineEvaluatedFiltering:
    def test_pe_lt20_ranks_passers_first_all_candidates_listed(self, stubbed, monkeypatch):
        """Partial-match contract: every candidate is listed; passers rank first."""
        _force_criteria(monkeypatch, [
            ScreenerFilter(field="pe_ratio", operator="<", value=20),
        ])
        resp = run_screener("PE<20", _config())
        assert resp.count == 3
        scores = [r.score for r in resp.results]
        assert scores == sorted(scores, reverse=True)
        # 600519 (pe=25) failed the only filter → lowest score, ranked last
        assert resp.results[-1].ticker == "600519"
        assert resp.results[0].score == 100.0
        # Strict pe semantics: 600519 (pe=25) did NOT match the filter
        matched_600519 = next(r for r in resp.results if r.ticker == "600519")
        assert matched_600519.match_details["pe_ratio"]["matched"] is False

    def test_pe_below_threshold_matches(self, stubbed, monkeypatch):
        """pe data now flows to the engine (legacy fetch-map gap fixed)."""
        _force_criteria(monkeypatch, [
            ScreenerFilter(field="pe_ratio", operator="<", value=20),
        ])
        resp = run_screener("PE<20", _config())
        by_ticker = {r.ticker: r for r in resp.results}
        assert by_ticker["000858"].match_details["pe_ratio"]["matched"] is True   # pe=15
        assert by_ticker["601318"].match_details["pe_ratio"]["matched"] is True   # pe=9
        assert by_ticker["600519"].match_details["pe_ratio"]["matched"] is False  # pe=25

    def test_chip_missing_ratio_passes_sentinel(self, stubbed, monkeypatch):
        """Legacy 'missing optional data does not disqualify' via pass-sentinel."""
        _force_criteria(monkeypatch, [
            ScreenerFilter(field="chip_distribution", operator=">=", value=50),
        ])
        resp = run_screener("获利盘>=50", _config())
        matched_000858 = next(r for r in resp.results if r.ticker == "000858")
        assert matched_000858.match_details["chip_distribution"]["matched"] is True
        matched_600519 = next(r for r in resp.results if r.ticker == "600519")
        assert matched_600519.match_details["chip_distribution"]["matched"] is True

    def test_chip_threshold_filters_low_ratio(self, stubbed, monkeypatch):
        _force_criteria(monkeypatch, [
            ScreenerFilter(field="chip_distribution", operator=">=", value=50),
        ])
        resp = run_screener("获利盘>=50", _config())
        matched_601318 = next(r for r in resp.results if r.ticker == "601318")
        assert matched_601318.match_details["chip_distribution"]["matched"] is False

    def test_industry_contains_single_value(self, stubbed, monkeypatch):
        _force_criteria(monkeypatch, [
            ScreenerFilter(field="industry", operator="in", value="消费"),
        ])
        resp = run_screener("消费股", _config())
        by_ticker = {r.ticker: r for r in resp.results}
        assert by_ticker["600519"].match_details["industry"]["matched"] is True
        assert by_ticker["601318"].match_details["industry"]["matched"] is False

    def test_industry_list_is_or_semantics(self, stubbed, monkeypatch):
        _force_criteria(monkeypatch, [
            ScreenerFilter(field="industry", operator="in", value=["消费", "金融"]),
        ])
        resp = run_screener("消费或金融", _config())
        by_ticker = {r.ticker: r for r in resp.results}
        assert by_ticker["600519"].match_details["industry"]["matched"] is True
        assert by_ticker["601318"].match_details["industry"]["matched"] is True


class TestContractPreserved:
    def test_unparseable_query_suggestion(self, stubbed, monkeypatch):
        monkeypatch.setattr(
            screener_service, "_parse_query_with_llm",
            lambda q, c: ScreenerCriteria(),
        )
        resp = run_screener("随便", _config())
        assert resp.count == 0
        assert "无法解析" in resp.suggestion

    def test_response_shape(self, stubbed, monkeypatch):
        _force_criteria(monkeypatch, [
            ScreenerFilter(field="pe_ratio", operator="<", value=20),
        ])
        resp = run_screener("PE<20", _config())
        assert resp.query == "PE<20"
        assert len(resp.parsed_criteria.filters) == 1
        assert "建议" in resp.suggestion or "找到" in resp.suggestion
        item = resp.results[0]
        assert {"ticker", "name", "pe", "score", "match_details"} <= set(
            item.model_dump().keys()
        )

    def test_ticker_hint_bypasses_universe(self, stubbed, monkeypatch):
        """Regression: ticker_hint previously hit an undefined name (NameError)."""
        _force_criteria(monkeypatch, [
            ScreenerFilter(field="pe_ratio", operator="<", value=20),
        ])
        resp = run_screener("PE<20", _config(), ticker_hint="600519")
        assert resp.count == 1
        assert resp.results[0].ticker == "600519"
        assert resp.results[0].match_details["pe_ratio"]["matched"] is False

    def test_max_results_limit(self, stubbed, monkeypatch):
        _force_criteria(monkeypatch, [
            ScreenerFilter(field="pe_ratio", operator="<", value=100),
        ])
        resp = run_screener("PE<100", _config(), max_results=2)
        assert resp.count == 2


class TestTemplateScreener:
    def test_unknown_template(self):
        resp = run_template_screener("nonexistent")
        assert resp.count == 0
        assert "未知" in resp.suggestion

    def test_known_template_runs_engine_pool(self, monkeypatch):
        import pandas as pd
        from tradingagents.screener_engine import ScreenerEngine

        pool = pd.DataFrame([
            {"ticker": "600519", "name": "贵州茅台", "pe_ratio": 25.0,
             "pb_ratio": 8.0, "market_cap": 2_000_000_000_000},
            {"ticker": "000858", "name": "五粮液", "pe_ratio": 9.0,
             "pb_ratio": 1.2, "market_cap": 5_000_000_000_000},
        ])
        monkeypatch.setattr(ScreenerEngine, "_get_stock_pool", lambda self: pool)

        resp = run_template_screener("low_pe", max_results=10)
        assert resp.query == "低估值"  # Template name
        assert resp.count >= 1
        tickers = [r.ticker for r in resp.results]
        assert "000858" in tickers
        assert "600519" not in tickers


class TestScreenerHTTPRoute:
    def test_template_id_routes_to_template_runner(self, monkeypatch):
        from fastapi.testclient import TestClient
        from tradingagents_api.server import app
        from tradingagents_api.screener import ScreenerResponse

        called = {}

        def fake_template(template_id, max_results):
            called["template_id"] = template_id
            return ScreenerResponse(query="低估值", parsed_criteria=ScreenerCriteria(),
                                    results=[], count=0, suggestion="模板未命中")

        from tradingagents_api.routers import screener as screener_router
        monkeypatch.setattr(screener_router, "run_template_screener", fake_template)
        resp = TestClient(app).post("/api/screener", json={"template_id": "low_pe"})
        assert resp.status_code == 200
        assert called["template_id"] == "low_pe"

    def test_query_routes_to_nl_runner(self, monkeypatch):
        from fastapi.testclient import TestClient
        from tradingagents_api.server import app
        from tradingagents_api.screener import ScreenerResponse

        called = {}

        def fake_nl(query, config, max_results, ticker_hint):
            called["query"] = query
            return ScreenerResponse(query=query, parsed_criteria=ScreenerCriteria(),
                                    results=[], count=0, suggestion="无法解析选股条件")

        from tradingagents_api.routers import screener as screener_router
        monkeypatch.setattr(screener_router, "run_screener", fake_nl)
        resp = TestClient(app).post("/api/screener", json={"query": "PE<20"})
        assert resp.status_code == 200
        assert called["query"] == "PE<20"


class TestLLMParsing:
    def test_parse_with_cache_roundtrip(self, tmp_path, monkeypatch):
        """The NL parse path works end-to-end and caches the LLM response
        (previously broken: CachedLLM was constructed without a cache)."""
        import json as _json

        calls = {"n": 0}

        class FakeLLM:
            def invoke(self, messages, config=None, **kwargs):
                calls["n"] += 1
                payload = _json.dumps({
                    "filters": [{"field": "pe_ratio", "operator": "<", "value": 20}],
                    "sort_by": None,
                    "ascending": False,
                })
                from langchain_core.messages import AIMessage
                return AIMessage(content=f"```json\n{payload}\n```")

        import tradingagents.llm_clients.factory as factory
        monkeypatch.setattr(factory, "create_quick_llm", lambda config, **kw: FakeLLM())

        config = {"llm_provider": "openai", "data_cache_dir": str(tmp_path)}
        criteria = screener_service._parse_query_with_llm("PE<20", config)
        assert len(criteria.filters) == 1
        assert criteria.filters[0].field == "pe_ratio"
        assert calls["n"] == 1

        # Second identical query served from cache — no new LLM call
        again = screener_service._parse_query_with_llm("PE<20", config)
        assert again.filters[0].field == "pe_ratio"
        assert calls["n"] == 1
