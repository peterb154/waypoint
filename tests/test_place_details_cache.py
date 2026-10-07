"""Pins the Place Details cache: a hit skips the paid HTTP call, a miss fetches
and stores, a failed fetch is NOT cached, and stale rows are refetched.
"""

from __future__ import annotations

import psycopg
import pytest

import cache
import places
import verdict

CANDIDATE = {"id": "pid-1", "name": "Indie Motel", "rating": 4.6, "reviews": 120,
             "lat": 39.2, "lon": -96.3}


@pytest.fixture
def fakes(monkeypatch):
    state = {"store": {}, "http": 0, "fail": False}

    def place_details(place_id):
        state["http"] += 1
        if state["fail"]:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return {"id": place_id, "name": "Indie Motel", "reviews": []}

    monkeypatch.setattr(places, "search_nearby", lambda *a, **kw: [dict(CANDIDATE)])
    monkeypatch.setattr(places, "place_details", place_details)
    monkeypatch.setattr(cache, "get_place_details", lambda pid: state["store"].get(pid))
    monkeypatch.setattr(cache, "store_place_details",
                        lambda pid, d: state["store"].__setitem__(pid, dict(d)))
    return state


def test_miss_fetches_and_stores_then_hit_skips_http(fakes):
    first, _ = verdict._gather(39.2, -96.3, ["motel"], 6)
    assert fakes["http"] == 1
    assert "pid-1" in fakes["store"]
    second, _ = verdict._gather(39.2, -96.3, ["motel"], 6)
    assert fakes["http"] == 1  # served from cache
    assert second[0]["name"] == first[0]["name"] == "Indie Motel"
    assert second[0]["lat"] == CANDIDATE["lat"]


def test_failed_fetch_is_not_cached(fakes):
    fakes["fail"] = True
    out, _ = verdict._gather(39.2, -96.3, ["motel"], 6)
    assert "error" in out[0]
    assert fakes["store"] == {}


def _db_or_skip():
    try:
        conn = cache.connect()
    except psycopg.OperationalError:
        pytest.skip("local Postgres not reachable")
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('place_details')")
        if cur.fetchone()[0] is None:
            conn.close()
            pytest.skip("place_details table not migrated")
    return conn


def test_stale_row_misses_fresh_row_hits():
    conn = _db_or_skip()
    pid = "test:place-details-ttl"
    try:
        cache.store_place_details(pid, {"name": "x"})
        assert cache.get_place_details(pid) == {"name": "x"}
        with conn.cursor() as cur:
            cur.execute("UPDATE place_details SET fetched_at = now() - interval '91 days' "
                        "WHERE place_id = %s", [pid])
        conn.commit()
        assert cache.get_place_details(pid, ttl_days=90) is None
        cache.store_place_details(pid, {"name": "y"})  # refetch overwrites + refreshes
        assert cache.get_place_details(pid) == {"name": "y"}
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM place_details WHERE place_id = %s", [pid])
        conn.commit()
        conn.close()
