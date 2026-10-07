"""Pins the mode-sharing cost win: a 2-mode sweep score fetches food and
attractions once per town, not once per mode. Only lodging differs by mode.
"""

from __future__ import annotations

import area
import cache
import places
import server

TOWN = {"name": "Wamego", "lat": 39.2019, "lon": -96.3050}


def _fake_places(monkeypatch, empty=()):
    calls = {"search": [], "details": 0}

    def search_nearby(lat, lon, included_types, **kw):
        kind = ("food" if included_types == places.FOOD_TYPES
                else "attractions" if included_types == places.ATTRACTION_TYPES
                else "lodging")
        calls["search"].append(kind)
        if kind in empty:
            return []
        return [{"id": f"{kind}-1", "name": f"Indie {kind}", "lat": lat, "lon": lon}]

    def place_details(place_id):
        calls["details"] += 1
        return {"id": place_id, "name": place_id}

    monkeypatch.setattr(places, "search_nearby", search_nearby)
    monkeypatch.setattr(places, "place_details", place_details)
    monkeypatch.setattr(cache, "get_place_details", lambda pid: None)
    monkeypatch.setattr(cache, "store_place_details", lambda pid, d: None)
    monkeypatch.setattr(area, "_judge", lambda *a, **kw: {"total": 5, "band": "acceptable"})
    return calls


def test_two_modes_share_food_and_attractions(monkeypatch):
    calls = _fake_places(monkeypatch)
    out, err = server._score_modes(TOWN, ["moto", "couple"], anchors=None)
    assert err is None
    assert [m for m, _ in out] == ["moto", "couple"]
    assert calls["search"].count("food") == 1
    assert calls["search"].count("attractions") == 1
    assert calls["search"].count("lodging") == 2
    # 1 food detail + 1 lodging detail per mode
    assert calls["details"] == 3


def test_no_modes_needed_costs_nothing(monkeypatch):
    calls = _fake_places(monkeypatch)
    assert server._score_modes(TOWN, [], anchors=None) == ([], None)
    assert calls["search"] == []


def test_filter_out_town_skips_attractions(monkeypatch):
    calls = _fake_places(monkeypatch, empty=("food", "lodging"))
    r = area.score_town(TOWN["name"], TOWN["lat"], TOWN["lon"], "moto")
    assert r["band"] == "filter-out"
    assert "attractions" not in calls["search"]


def test_single_mode_cli_path_still_gathers(monkeypatch):
    calls = _fake_places(monkeypatch)
    area.score_town(TOWN["name"], TOWN["lat"], TOWN["lon"], "couple")
    assert sorted(calls["search"]) == ["attractions", "food", "lodging"]


def test_attractions_fetched_once_when_only_second_mode_reaches_judge(monkeypatch):
    # Moto finds nothing (no food, B&B types excluded) -> filter-out; couple finds a
    # B&B, so the lazy attractions fetch happens on the second mode, exactly once.
    calls = _fake_places(monkeypatch, empty=("food",))
    real = places.search_nearby

    def search_nearby(lat, lon, included_types, **kw):
        if "bed_and_breakfast" not in included_types and included_types not in (
                places.FOOD_TYPES, places.ATTRACTION_TYPES):
            calls["search"].append("lodging")
            return []  # moto lodging: nothing
        return real(lat, lon, included_types, **kw)

    monkeypatch.setattr(places, "search_nearby", search_nearby)
    results, _ = server._score_modes(TOWN, ["moto", "couple"], anchors=None)
    out = dict(results)
    assert out["moto"]["band"] == "filter-out"
    assert out["couple"]["band"] == "acceptable"
    assert calls["search"].count("attractions") == 1
