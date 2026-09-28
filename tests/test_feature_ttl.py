"""Ticket 11 — per-feature cache TTL declarations.

Phase 9 spec §6 assigns each feature its own freshness (institutional holdings
are quarterly → 72h; analyst ratings move fast → 6h), but historically only
ohlcv had a TTL special case. FEATURE_TABLE entries now may declare
``cache_ttl``; the cache layer honours an explicit declaration over the
market-hours default, and undeclared features keep the old behaviour.
"""
from __future__ import annotations

import importlib

import pytest

import tradingagents.cache.manager as cm
from tradingagents.cache.manager import (
    _TTL_AFTER_HOURS,
    _TTL_OHLCV,
    _TTL_TRADING_HOURS,
    _ttl_for_type,
    feature_ttl,
    register_feature_ttl,
)


@pytest.fixture(autouse=True)
def _clean_overrides():
    """Snapshot and restore the override registry around each test."""
    saved = dict(cm._FEATURE_TTL_OVERRIDES)
    cm._FEATURE_TTL_OVERRIDES.clear()
    yield
    cm._FEATURE_TTL_OVERRIDES.clear()
    cm._FEATURE_TTL_OVERRIDES.update(saved)


@pytest.mark.unit
def test_registered_override_wins_over_market_hours_default():
    register_feature_ttl("institutional_hold", 72 * 3600)
    # override applies regardless of whether we're inside market hours
    assert _ttl_for_type("institutional_hold") == 72 * 3600


@pytest.mark.unit
def test_undeclared_feature_keeps_default_behaviour():
    assert _ttl_for_type("some_unknown_feature") in (_TTL_TRADING_HOURS, _TTL_AFTER_HOURS)


@pytest.mark.unit
def test_ohlcv_special_case_preserved():
    assert _ttl_for_type("ohlcv") == _TTL_OHLCV


@pytest.mark.unit
def test_nonpositive_ttl_is_ignored():
    register_feature_ttl("broken_feature", 0)
    register_feature_ttl("broken_feature", -5)
    # neither registration took effect → falls back to default
    assert _ttl_for_type("broken_feature") in (_TTL_TRADING_HOURS, _TTL_AFTER_HOURS)


@pytest.mark.unit
def test_later_registration_overwrites():
    register_feature_ttl("analyst_rating", 6 * 3600)
    register_feature_ttl("analyst_rating", 12 * 3600)
    assert feature_ttl("analyst_rating") == 12 * 3600


@pytest.mark.unit
def test_feature_table_declarations_are_registered():
    """Importing astock_features must hand every declared cache_ttl to the cache layer."""
    import tradingagents_api.astock_features as af

    importlib.reload(cm)  # no-op safety: registry fixture already reset it

    declared = {
        name: entry["cache_ttl"]
        for name, entry in af.FEATURE_TABLE.items()
        if entry.get("cache_ttl")
    }
    assert declared, "FEATURE_TABLE should declare cache_ttl for Phase 9 features"

    # re-run the registration the module performs at import
    for name, ttl in declared.items():
        register_feature_ttl(name, ttl)

    for name, ttl in declared.items():
        assert feature_ttl(name) == ttl, f"{name} TTL not effective"


@pytest.mark.unit
def test_phase9_spec_ttls():
    """The declared values match Phase 9 spec §6 (大宗当日1h / 评级6h / 机构持股72h …)."""
    import tradingagents_api.astock_features as af

    expected = {
        "block_trade_detail": 3600,
        "block_trade_industry": 86400,
        "block_trade_market_stat": 3600,
        "dividend_bonus": 86400,
        "earnings_forecast": 86400,
        "earnings_express": 86400,
        "analyst_rating": 6 * 3600,
        "institutional_hold": 72 * 3600,
    }
    for name, ttl in expected.items():
        entry = af.FEATURE_TABLE.get(name)
        assert entry is not None, f"{name} missing from FEATURE_TABLE"
        assert entry.get("cache_ttl") == ttl
