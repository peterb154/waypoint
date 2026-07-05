"""Ad-hoc region scan: score towns within 50 mi of a center and rank them.
Reuses the verdict.py pipeline. Manual preview of Phase 3/4 corridor batch.

- MODE: moto (B&Bs excluded) — this is an 8-dudes trip.
- Nearest-anchor attribution: each lodging/food place counts only for its closest
  town, so satellites (East Dubuque) don't borrow a big neighbor's (Dubuque) hotels.
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import places  # noqa: E402
from chains import filter_independents  # noqa: E402
from verdict import TOP_N_FOOD, TOP_N_LODGING, _judge  # noqa: E402

CENTER = (42.5006, -90.6645)  # Dubuque, IA
RADIUS_MI = 50.0
MODE = "moto"

CANDIDATES = [
    "Dubuque, IA",  # anchor + scored (hub)
    "Galena, IL", "East Dubuque, IL", "Elizabeth, IL", "Stockton, IL", "Hanover, IL",
    "Platteville, WI", "Dickeyville, WI", "Cuba City, WI", "Lancaster, WI", "Potosi, WI",
    "Shullsburg, WI", "Cassville, WI",
    "Dyersville, IA", "Bellevue, IA", "Guttenberg, IA", "Elkader, IA", "Maquoketa, IA",
    "Cascade, IA", "Manchester, IA", "Bernard, IA",
]

# moto lodging types (B&Bs dropped from both included and excluded)
LODGING_TYPES = [t for t in places.LODGING_TYPES if t not in places.LODGING_BNB_TYPES]
LODGING_EXCL = list(places.LODGING_EXCLUDE_TYPES) + places.LODGING_BNB_TYPES


def haversine_mi(a, b):
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


# 1) geocode + distance filter
anchors = []  # (name, lat, lon) for every town within radius (attribution set)
for name in CANDIDATES:
    try:
        lat, lon, _ = places.geocode(name)
    except Exception as e:  # noqa: BLE001
        print(f"  SKIP {name}: geocode failed ({e})")
        continue
    d = haversine_mi(CENTER, (lat, lon))
    if d <= RADIUS_MI:
        anchors.append((name, lat, lon))
    print(f"  [{'IN ' if d <= RADIUS_MI else 'out'}] {name:<18} {d:5.1f} mi")
    time.sleep(1)

print(f"\nScoring {len(anchors)} towns within {RADIUS_MI:.0f} mi "
      f"(mode={MODE}, attribution on)...\n")


def nearest_anchor(clat, clon):
    return min(anchors, key=lambda a: haversine_mi((a[1], a[2]), (clat, clon)))[0]


def gather_attributed(town, lat, lon, included, top_n, excluded=None):
    """search -> keep only places whose NEAREST anchor is this town -> chain
    filter -> details on the best few."""
    cands = places.search_nearby(lat, lon, included, excluded_types=excluded)
    mine = [
        c for c in cands
        if c.get("lat") is None or nearest_anchor(c["lat"], c["lon"]) == town
    ]
    keep, _ = filter_independents(mine)
    keep.sort(
        key=lambda c: (
            places.weighted_rating(c.get("rating"), c.get("reviews")),
            (c.get("reviews") or 0),
        ),
        reverse=True,
    )
    out = []
    for c in keep[:top_n]:
        try:
            d = places.place_details(c["id"])
        except Exception:  # noqa: BLE001
            d = {"name": c["name"], "rating": c.get("rating")}
        d["lat"], d["lon"] = c.get("lat"), c.get("lon")
        out.append(d)
    return out


# 2) score each
results = []
for name, lat, lon in anchors:
    try:
        lodging = gather_attributed(name, lat, lon, LODGING_TYPES, TOP_N_LODGING, LODGING_EXCL)
        food = gather_attributed(name, lat, lon, places.FOOD_TYPES, TOP_N_FOOD)
        attractions = places.search_nearby(
            lat, lon, places.ATTRACTION_TYPES, radius_m=8000.0, max_results=15
        )
        r = _judge(name, lodging, food, attractions, MODE)
        results.append((name, r))
        bl = (r.get("best_lodging") or {}).get("name", "?")
        print(f"  scored {name:<18} {r.get('total')}/10  {r.get('band')}  ({bl})")
    except Exception as e:  # noqa: BLE001
        print(f"  ERROR {name}: {e}")

# 3) rank
print("\n" + "=" * 78)
print(f"MOST SUITABLE TOWNS WITHIN {RADIUS_MI:.0f} MI OF DUBUQUE  (8-dudes / moto, no B&B)")
print("=" * 78)
for name, r in sorted(results, key=lambda x: (x[1].get("total") or 0), reverse=True):
    bl = (r.get("best_lodging") or {}).get("name", "?")
    print(f"{r.get('total'):>4}/10  [{r.get('band'):<12}] {name:<18} — {bl}")
    print(f"          {r.get('reason')}")
