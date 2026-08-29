"""Unit tests for tradingagents.data_cache (DataCache + make_cache_key)."""

from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

from tradingagents.data_cache import DataCache, make_cache_key


# ── make_cache_key ────────────────────────────────────────────────────────────

class TestMakeCacheKey:
    def test_deterministic(self):
        k1 = make_cache_key("ohlcv", ticker="600519", start="2026-01-01", end="2026-08-28")
        k2 = make_cache_key("ohlcv", ticker="600519", start="2026-01-01", end="2026-08-28")
        assert k1 == k2

    def test_different_params_different_keys(self):
        k1 = make_cache_key("ohlcv", ticker="600519", start="2026-01-01")
        k2 = make_cache_key("ohlcv", ticker="600519", start="2026-02-01")
        assert k1 != k2

    def test_different_types_different_keys(self):
        k1 = make_cache_key("ohlcv", ticker="600519")
        k2 = make_cache_key("indicator", ticker="600519")
        assert k1 != k2

    def test_key_format(self):
        key = make_cache_key("ohlcv", ticker="600519")
        assert key.startswith("ohlcv:")
        # Hash portion is 32 hex chars
        hash_part = key.split(":", 1)[1]
        assert len(hash_part) == 32
        assert all(c in "0123456789abcdef" for c in hash_part)

    def test_unicode_params(self):
        k1 = make_cache_key("feature", name="筹码分布")
        k2 = make_cache_key("feature", name="筹码分布")
        assert k1 == k2


# ── DataCache ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_cache(tmp_path):
    """Provide a DataCache backed by a temp directory."""
    cache = DataCache(tmp_path, "TEST")
    yield cache
    cache.close()


class TestDataCacheBasic:
    def test_set_and_get(self, tmp_cache):
        tmp_cache.set("key1", {"price": 100.5}, "ohlcv")
        result = tmp_cache.get("key1")
        assert result == {"price": 100.5}

    def test_get_miss(self, tmp_cache):
        assert tmp_cache.get("nonexistent") is None

    def test_overwrite(self, tmp_cache):
        tmp_cache.set("key1", {"v": 1}, "test")
        tmp_cache.set("key1", {"v": 2}, "test")
        assert tmp_cache.get("key1") == {"v": 2}

    def test_has(self, tmp_cache):
        assert tmp_cache.has("key1") is False
        tmp_cache.set("key1", {"v": 1}, "test")
        assert tmp_cache.has("key1") is True

    def test_clear_all(self, tmp_cache):
        tmp_cache.set("a", {"v": 1}, "t1")
        tmp_cache.set("b", {"v": 2}, "t2")
        cleared = tmp_cache.clear()
        assert cleared == 2
        assert tmp_cache.get("a") is None
        assert tmp_cache.get("b") is None

    def test_clear_by_type(self, tmp_cache):
        tmp_cache.set("a", {"v": 1}, "ohlcv")
        tmp_cache.set("b", {"v": 2}, "indicator")
        tmp_cache.set("c", {"v": 3}, "ohlcv")
        cleared = tmp_cache.clear("ohlcv")
        assert cleared == 2
        assert tmp_cache.get("a") is None
        assert tmp_cache.get("c") is None
        assert tmp_cache.get("b") == {"v": 2}


class TestDataCacheTTL:
    def test_expired_entry_returns_none(self, tmp_cache):
        tmp_cache.set("key1", {"v": 1}, "test")
        # Manually backdate the entry
        tmp_cache._conn.execute(
            "UPDATE data_cache SET created_at = ? WHERE cache_key = ?",
            (time.time() - 7200, "key1"),  # 2 hours ago
        )
        tmp_cache._conn.commit()

        # With 1-hour TTL, should be expired
        result = tmp_cache.get("key1", ttl_seconds=3600)
        assert result is None

    def test_valid_entry_within_ttl(self, tmp_cache):
        tmp_cache.set("key1", {"v": 1}, "test")
        # Entry is brand new; 1-hour TTL should be fine
        result = tmp_cache.get("key1", ttl_seconds=3600)
        assert result == {"v": 1}

    def test_lazy_deletion(self, tmp_cache):
        tmp_cache.set("key1", {"v": 1}, "test")
        # Backdate
        tmp_cache._conn.execute(
            "UPDATE data_cache SET created_at = ? WHERE cache_key = ?",
            (time.time() - 7200, "key1"),
        )
        tmp_cache._conn.commit()

        tmp_cache.get("key1", ttl_seconds=3600)  # should trigger lazy delete
        # Verify it's actually deleted from the DB
        row = tmp_cache._conn.execute(
            "SELECT COUNT(*) FROM data_cache WHERE cache_key = ?", ("key1",)
        ).fetchone()
        assert row[0] == 0


class TestDataCachePrune:
    def test_prune_expired(self, tmp_cache):
        tmp_cache.set("old", {"v": 1}, "test")
        tmp_cache.set("new", {"v": 2}, "test")
        # Backdate "old" entry beyond 24h
        cutoff = time.time() - 86401
        tmp_cache._conn.execute(
            "UPDATE data_cache SET created_at = ? WHERE cache_key = ?",
            (cutoff, "old"),
        )
        tmp_cache._conn.commit()

        pruned = tmp_cache.prune_expired()
        assert pruned == 1
        assert tmp_cache.get("old") is None
        assert tmp_cache.get("new") == {"v": 2}


class TestDataCacheStats:
    def test_stats_empty(self, tmp_cache):
        s = tmp_cache.stats()
        assert s["total_entries"] == 0
        assert s["hits"] == 0
        assert s["misses"] == 0

    def test_stats_after_operations(self, tmp_cache):
        tmp_cache.set("a", {"v": 1}, "ohlcv")
        tmp_cache.set("b", {"v": 2}, "indicator")
        tmp_cache.get("a")  # hit
        tmp_cache.get("nonexistent")  # miss

        s = tmp_cache.stats()
        assert s["total_entries"] == 2
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["by_type"]["ohlcv"] == 1
        assert s["by_type"]["indicator"] == 1


class TestDataCacheContextManager:
    def test_context_manager(self, tmp_path):
        with DataCache(tmp_path, "CTX") as cache:
            cache.set("k", {"v": 1}, "test")
            assert cache.get("k") == {"v": 1}
        # Connection should be closed after exiting context


class TestDataCachePersistence:
    def test_data_persists_across_instances(self, tmp_path):
        cache1 = DataCache(tmp_path, "PERSIST")
        cache1.set("key1", {"value": 42}, "test")
        cache1.close()

        cache2 = DataCache(tmp_path, "PERSIST")
        result = cache2.get("key1")
        assert result == {"value": 42}
        cache2.close()
