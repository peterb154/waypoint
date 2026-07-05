"""Area search with caching.

    uv run python area.py "Dubuque, IA" 30 [--couple] [--limit N]

Enumerate reference towns within a radius (PostGIS), score only the ones not
already cached (moto vs couple scored/cached separately), store every result
(failures too), and print a ranked shortlist. Re-running an area is then free.
"""

from __future__ import annotations

import math
import sys

from dotenv import load_dotenv

import cache
import places
from verdict import TOP_N_FOOD, TOP_N_LODGING, _gather, _judge

load_dotenv(override=True)


def score_town(name: str, lat: float, lon: float, mode: str, anchors=None) -> dict:
    """Independent per-town score (cacheable): its own lodging/food within radius.

    anchors: [(town_name, lat, lon), ...] of nearby reference towns. When given,
    each venue is attributed to its nearest anchor, so a town only scores on the
    venues physically closest to it (a neighbour's motel/restaurant/attraction no
    longer counts here). None = no attribution (single-town CLI use)."""
    keep_here = _nearest_filter(name, lat, lon, anchors)
    lodging_types = list(places.LODGING_TYPES)
    lodging_excl = list(places.LODGING_EXCLUDE_TYPES)
    if mode == "moto":
        lodging_types = [t for t in lodging_types if t not in places.LODGING_BNB_TYPES]
        lodging_excl += places.LODGING_BNB_TYPES
    lodging, _ = _gather(lat, lon, lodging_types, TOP_N_LODGING,
                         excluded_types=lodging_excl, keep_here=keep_here)
    food, _ = _gather(lat, lon, places.FOOD_TYPES, TOP_N_FOOD, keep_here=keep_here)
    if not lodging and not food:
        return {
            "total": 0, "band": "filter-out", "scores": {}, "best_lodging": None,
            "food": [], "reason": "No independent lodging or food found.", "tip": "",
        }
    attractions = places.search_nearby(
        lat, lon, places.ATTRACTION_TYPES, radius_m=8000.0, max_results=15
    )
    if keep_here is not None:
        attractions = [a for a in attractions
                       if a.get("lat") is None or keep_here(a["lat"], a["lon"])]
    r = _judge(name, lodging, food, attractions, mode)
    # Tag every named place with its coords (matched from the detail lists), for
    # dedupe + so each location gets a Street View link / GPS coords in the UI.
    bl = r.get("best_lodging") or {}
    if bl.get("name"):
        d = next((x for x in lodging if x.get("name") == bl["name"]), None)
        if d:
            bl["lat"], bl["lon"] = d.get("lat"), d.get("lon")
            r["best_lodging"] = bl
    for item in r.get("food") or []:
        d = next((x for x in food if x.get("name") == item.get("name")), None)
        if d:
            item["lat"], item["lon"] = d.get("lat"), d.get("lon")
    return r


def area_search(center: str, radius_mi: float, mode: str, limit: int | None = None,
                refresh: bool = False):
    lat, lon, display = places.geocode(center)
    print(f"\n=== area: {center}  ({radius_mi:.0f} mi, mode={mode}) ===")
    print(f"center: {display}  ({lat:.4f}, {lon:.4f})\n")

    conn = cache.connect()
    candidates = cache.towns_within(conn, lat, lon, radius_mi)
    # Attribution set: every reference town in the area (before --limit), so each
    # venue is credited to its nearest town and neighbours don't share venues.
    anchors = [(c["name"], c["lat"], c["lon"]) for c in candidates]
    if limit:
        candidates = candidates[:limit]
    print(f"{len(candidates)} candidate towns from reference table\n")

    hits = scored = 0
    results = []
    for c in candidates:
        cached = None if refresh else cache.get_cached(conn, c["name"], c["state"], mode)
        if cached:
            r, src = cached, "cache"
            hits += 1
        else:
            r = score_town(c["name"], c["lat"], c["lon"], mode, anchors=anchors)
            cache.store_verdict(conn, c["name"], c["state"], c["geoid"], mode,
                                c["lat"], c["lon"], r)
            src = "scored"
            scored += 1
        results.append((c, r, src))
        print(f"  [{src:>6}] {c['name']+', '+c['state']:<22} {r.get('total')}/10  {r.get('band')}")

    conn.close()
    print(f"\ncache hits: {hits}   newly scored: {scored}")

    deduped = _dedupe(results)
    print("\n" + "=" * 70)
    print(f"RANKED — {center} within {radius_mi:.0f} mi  ({mode})")
    print("=" * 70)
    ranked = sorted(deduped, key=lambda x: (x[1].get("total") or 0), reverse=True)
    for c, r, _src, others in ranked:
        bl = r.get("best_lodging") or {}
        blname = bl.get("name") if isinstance(bl, dict) else None
        also = f"   (+{len(others)} satellites: {', '.join(others)})" if others else ""
        print(f"{r.get('total'):>4}/10  [{r.get('band'):<12}] {c['name']+', '+c['state']:<22}"
              f" ({c['mi']:.0f} mi)  {blname or ''}{also}")


def _nearest_filter(name, lat, lon, anchors):
    """Build keep(vlat, vlon) -> True iff `name` is the nearest anchor town to the
    venue. Guarantees the town itself is an anchor (else it would keep nothing).
    Returns None when no anchors are given (attribution disabled)."""
    if not anchors:
        return None
    pts = list(anchors)
    if not any(a[0] == name for a in pts):
        pts.append((name, lat, lon))

    def keep(vlat, vlon):
        return min(pts, key=lambda a: _haversine_mi(vlat, vlon, a[1], a[2]))[0] == name

    return keep


def _haversine_mi(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _dedupe(results):
    """Fold towns that share one physical lodging into the town nearest it (the
    owner); the rest are listed as satellites. Returns [(town, verdict, src, others)]."""
    groups: dict = {}
    out = []
    for c, r, src in results:
        bl = r.get("best_lodging") or {}
        name, blat = bl.get("name"), bl.get("lat")
        if not name or blat is None:
            out.append((c, r, src, []))          # filter-outs / no shared lodging
        else:
            groups.setdefault(name, []).append((c, r, src, blat, bl.get("lon")))
    for _name, members in groups.items():
        owner = min(members, key=lambda m: _haversine_mi(m[0]["lat"], m[0]["lon"], m[3], m[4]))
        others = [m[0]["name"] for m in members if m is not owner]
        out.append((owner[0], owner[1], owner[2], others))
    return out


def main() -> int:
    argv = sys.argv[1:]
    flags = {a for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2:
        print('usage: python area.py "Center, ST" <radius_mi> [--couple] [--limit N]')
        return 2
    center, radius = pos[0], float(pos[1])
    mode = "couple" if ({"--couple", "--car"} & flags) else "moto"
    refresh = "--refresh" in flags
    limit = None
    for a in argv:
        if a.startswith("--limit"):
            limit = int(a.split("=")[1]) if "=" in a else int(pos[2])
    area_search(center, radius, mode, limit, refresh=refresh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
