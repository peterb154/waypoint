"""Pins daily-quota handling: a per-day 429 is not retried, isn't swallowed into
stub details, stops the sweep job, and keeps any verdict already scored."""

from __future__ import annotations

import json
import threading

import httpx
import pytest

import area
import cache
import places
import server
import verdict

# The shape of Google's per-day quota 429 (google.rpc.Status + ErrorInfo).
DAILY_429 = json.dumps({"error": {
    "code": 429, "status": "RESOURCE_EXHAUSTED",
    "message": "Quota exceeded for quota metric 'GetPlace requests' and limit 'GetPlace "
               "requests per day' of service 'places.googleapis.com' for consumer "
               "'project_number:1'.",
    "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
                 "reason": "RATE_LIMIT_EXCEEDED", "domain": "googleapis.com",
                 "metadata": {"quota_limit": "GetPlaceRequestPerDayPerProject",
                              "service": "places.googleapis.com"}}],
}})
PER_MINUTE_429 = json.dumps({"error": {
    "code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded (per minute).",
    "details": [{"metadata": {"quota_limit": "SearchNearbyRequestPerMinutePerProject"}}],
}})


def _resp(status, text=""):
    return httpx.Response(status, text=text, request=httpx.Request("GET", "https://x"))


def test_daily_quota_429_raises_without_retry(monkeypatch):
    monkeypatch.setattr(places.time, "sleep", lambda s: None)
    sends = []
    with pytest.raises(places.QuotaExhausted):
        places._send_with_retry(lambda: sends.append(1) or _resp(429, DAILY_429))
    assert len(sends) == 1


def test_daily_quota_detected_from_metadata_alone():
    body = json.dumps({"error": {"code": 429, "message": "Quota exceeded.", "details": [
        {"metadata": {"quota_limit": "SearchNearbyRequestPerDayPerProject"}}]}})
    assert places._is_daily_quota(_resp(429, body))


def test_per_minute_429_still_retries(monkeypatch):
    monkeypatch.setattr(places.time, "sleep", lambda s: None)
    replies = iter([_resp(429, PER_MINUTE_429), _resp(200, "{}")])
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
    def __init__(self):
        self.sql = []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sql.append(sql)


def _towns(*names):
    return [{"name": n, "state": "KS", "geoid": n, "lat": 1, "lon": 2} for n in names]


def _patch_cache(monkeypatch, towns, stored):
    monkeypatch.setattr(cache, "towns_within", lambda *a, **kw: towns)
    monkeypatch.setattr(cache, "get_cached", lambda *a, **kw: None)
    monkeypatch.setattr(cache, "store_verdict",
                        lambda conn, town, st, g, mode, *a: stored.append((town, mode)))


def test_quota_stops_job_but_stores_in_flight_towns(monkeypatch):
    # A hits quota after scoring moto; B is mid-flight and finishes after. Both
    # towns' finished verdicts must be stored before the job stops.
    stored = []
    _patch_cache(monkeypatch, _towns("A", "B"), stored)
    a_done, b_started = threading.Event(), threading.Event()

    def score_modes(t, modes, anchors):
        if t["name"] == "A":
            b_started.wait(2)
            a_done.set()
            return [("moto", {"total": 6})], places.QuotaExhausted("quota")
        b_started.set()
        a_done.wait(2)
        return [("moto", {"total": 5}), ("couple", {"total": 7})], None

    monkeypatch.setattr(server, "_score_modes", score_modes)
    with pytest.raises(places.QuotaExhausted):
        server._run_job(_Conn(), 1, 1, 2, 10)
    assert sorted(stored) == [("A", "moto"), ("B", "couple"), ("B", "moto")]


def test_ordinary_error_skips_town_and_job_finishes(monkeypatch):
    stored = []
    _patch_cache(monkeypatch, _towns("A", "B"), stored)
    monkeypatch.setattr(server, "_score_modes", lambda t, modes, anchors: (
        ([], ValueError("bedrock hiccup")) if t["name"] == "A"
        else ([("moto", {"total": 5})], None)))
    conn = _Conn()
    server._run_job(conn, 1, 1, 2, 10)
    assert stored == [("B", "moto")]
    assert any("status = 'done'" in q for q in conn.sql)
