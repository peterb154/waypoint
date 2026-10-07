"""Pins daily-quota handling: a per-day 429 is not retried, isn't swallowed into
stub details, stops the sweep job, and keeps any verdict already scored."""

from __future__ import annotations

import httpx
import pytest

import area
import cache
import places
import server
import verdict

DAILY_429 = ("Quota exceeded for quota metric 'GetPlace requests' and limit "
             "'GetPlace requests per day' of service 'places.googleapis.com'")


def _resp(status, text=""):
    return httpx.Response(status, text=text, request=httpx.Request("GET", "https://x"))


def test_daily_quota_429_raises_without_retry(monkeypatch):
    monkeypatch.setattr(places.time, "sleep", lambda s: None)
    sends = []
    with pytest.raises(places.QuotaExhausted):
        places._send_with_retry(lambda: sends.append(1) or _resp(429, DAILY_429))
    assert len(sends) == 1


def test_per_minute_429_still_retries(monkeypatch):
    monkeypatch.setattr(places.time, "sleep", lambda s: None)
    replies = iter([_resp(429, "per minute"), _resp(200, "{}")])
    assert places._send_with_retry(lambda: next(replies)).status_code == 200


def test_gather_does_not_swallow_quota(monkeypatch):
    def out_of_quota(pid):
        raise places.QuotaExhausted("quota")

    monkeypatch.setattr(places, "search_nearby",
                        lambda *a, **kw: [{"id": "p", "name": "Indie", "lat": 1, "lon": 2}])
    monkeypatch.setattr(places, "place_details", out_of_quota)
    monkeypatch.setattr(cache, "get_place_details", lambda *a, **kw: None)
    with pytest.raises(places.QuotaExhausted):
        verdict._gather(1, 2, ["motel"], 6)


def test_second_mode_failure_keeps_first_verdict(monkeypatch):
    monkeypatch.setattr(area, "gather_shared", lambda *a, **kw: {"food": [], "attractions": []})

    def score_town(name, lat, lon, mode, **kw):
        if mode == "couple":
            raise places.QuotaExhausted("quota")
        return {"total": 6, "band": "acceptable"}

    monkeypatch.setattr(area, "score_town", score_town)
    out, err = server._score_modes({"name": "X", "lat": 1, "lon": 2}, ["moto", "couple"], None)
    assert out == [("moto", {"total": 6, "band": "acceptable"})]
    assert isinstance(err, places.QuotaExhausted)


class _Conn:
    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.last = sql


def test_quota_stops_job_after_storing_partial(monkeypatch):
    towns = [{"name": "A", "state": "KS", "geoid": "1", "lat": 1, "lon": 2}]
    stored = []
    monkeypatch.setattr(cache, "towns_within", lambda *a, **kw: towns)
    monkeypatch.setattr(cache, "get_cached", lambda *a, **kw: None)
    monkeypatch.setattr(cache, "store_verdict",
                        lambda conn, town, st, g, mode, *a: stored.append(mode))
    monkeypatch.setattr(server, "_score_modes", lambda t, modes, anchors: (
        [("moto", {"total": 6})], places.QuotaExhausted("quota")))
    with pytest.raises(places.QuotaExhausted):
        server._run_job(_Conn(), 1, 1, 2, 10)
    assert stored == ["moto"]
