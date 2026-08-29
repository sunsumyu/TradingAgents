"""HTTP contract tests for the watchlist sync router (ticket #5).

The server is the merge authority: PUT applies client state with
newer-wins-by-updated_at and explicit tombstone deletions, then returns
the merged full state (one idempotent round-trip for the GUI).
"""

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tradingagents_api import watchlist as watchlist_service
from tradingagents_api.server import app


@pytest.fixture()
def client(tmp_path):
    fake_db = tmp_path / "watchlist.db"
    with patch.object(watchlist_service, "WATCHLIST_DB", fake_db):
        yield TestClient(app)


def _put(client, **overrides):
    payload = {
        "groups": [
            {
                "id": "g1",
                "name": "自选股",
                "position": 0,
                "collapsed": False,
                "updated_at": 100,
                "items": [
                    {"ticker": "600519", "name": "贵州茅台", "position": 0, "updated_at": 100},
                ],
            },
        ],
        "deleted_group_ids": [],
        "deleted_items": [],
    }
    payload.update(overrides)
    return client.put("/api/watchlist", json=payload)


class TestSyncLifecycle:
    def test_put_then_get_roundtrip(self, client):
        resp = _put(client)
        assert resp.status_code == 200
        state = resp.json()
        assert len(state["groups"]) == 1
        group = state["groups"][0]
        assert group["id"] == "g1"
        assert group["name"] == "自选股"
        assert group["items"][0]["ticker"] == "600519"

        # Empty PUT (fresh device) returns the server state unchanged
        again = client.put("/api/watchlist", json={
            "groups": [], "deleted_group_ids": [], "deleted_items": [],
        }).json()
        assert again == state

    def test_newer_group_name_wins(self, client):
        _put(client)
        resp = _put(client, groups=[{
            "id": "g1", "name": "重点跟踪", "position": 0, "collapsed": True,
            "updated_at": 200, "items": [],
        }])
        group = resp.json()["groups"][0]
        assert group["name"] == "重点跟踪"
        assert group["collapsed"] is True

    def test_older_group_name_loses(self, client):
        _put(client, groups=[{
            "id": "g1", "name": "最新", "position": 0, "collapsed": False,
            "updated_at": 300, "items": [],
        }])
        resp = _put(client, groups=[{
            "id": "g1", "name": "过期改名", "position": 0, "collapsed": False,
            "updated_at": 100, "items": [],
        }])
        assert resp.json()["groups"][0]["name"] == "最新"

    def test_items_merge_without_duplicates(self, client):
        _put(client)
        # Same group, one existing ticker re-sent + one new ticker
        resp = _put(client, groups=[{
            "id": "g1", "name": "自选股", "position": 0, "collapsed": False,
            "updated_at": 100,
            "items": [
                {"ticker": "600519", "name": "贵州茅台改", "position": 1, "updated_at": 150},
                {"ticker": "000858", "name": "五粮液", "position": 2, "updated_at": 150},
            ],
        }])
        items = resp.json()["groups"][0]["items"]
        tickers = sorted(i["ticker"] for i in items)
        assert tickers == ["000858", "600519"]
        by_ticker = {i["ticker"]: i for i in items}
        assert by_ticker["600519"]["name"] == "贵州茅台改"  # newer wins

    def test_item_move_between_groups(self, client):
        _put(client)
        payload = {
            "groups": [
                {
                    "id": "g2", "name": "次选", "position": 1, "collapsed": False,
                    "updated_at": 200,
                    "items": [{"ticker": "600519", "name": "贵州茅台", "position": 0,
                               "updated_at": 200}],
                },
            ],
            "deleted_group_ids": [],
            "deleted_items": [{"group_id": "g1", "ticker": "600519",
                               "updated_at": 200}],
        }
        resp = client.put("/api/watchlist", json=payload)
        state = resp.json()
        groups = {g["id"]: g for g in state["groups"]}
        assert "600519" not in [i["ticker"] for i in groups["g1"]["items"]]
        assert "600519" in [i["ticker"] for i in groups["g2"]["items"]]

    def test_tombstone_group_deletion(self, client):
        _put(client, groups=[
            {"id": "g1", "name": "自选股", "position": 0, "collapsed": False,
             "updated_at": 100, "items": []},
            {"id": "g9", "name": "待删", "position": 1, "collapsed": False,
             "updated_at": 100, "items": []},
        ])
        resp = client.put("/api/watchlist", json={
            "groups": [],
            "deleted_group_ids": ["g9"],
            "deleted_items": [],
        })
        ids = [g["id"] for g in resp.json()["groups"]]
        assert "g9" not in ids
        assert "g1" in ids


class TestPersistence:
    def test_state_survives_reconnect(self, client, tmp_path):
        _put(client)
        # New client instance against the same DB file (simulates restart)
        with patch.object(watchlist_service, "WATCHLIST_DB",
                          tmp_path / "watchlist.db"):
            state = TestClient(app).get("/api/watchlist").json()
        assert state["groups"][0]["items"][0]["ticker"] == "600519"
