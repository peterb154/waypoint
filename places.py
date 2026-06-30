"""Google Places API (New) client + geocoding for the Phase 1 bare loop.

Two-step cost discipline (per the brief): cheap Nearby Search to get
candidates, then Place Details only on survivors of the chain filter.

- geocode(town)            -> (lat, lon, display_name)   [free, OSM Nominatim]
- search_nearby(...)       -> [candidate dict]            [cheap field mask]
- place_details(place_id)  -> dict                        [rich: reviews, website]
"""

from __future__ import annotations

import os

import httpx

PLACES_BASE = "https://places.googleapis.com/v1"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "motel-db/phase1 (+https://github.com/peterb154/motel-db)"

# Lodging-ish place types worth looking at (Places API New type table).
LODGING_TYPES = [
    "lodging",
    "hotel",
    "motel",
    "inn",
    "bed_and_breakfast",
    "guest_house",
    "cottage",
    "resort_hotel",
    "extended_stay_hotel",
]
FOOD_TYPES = ["restaurant", "diner", "cafe", "meal_takeaway", "bar_and_grill"]

# These carry the generic "lodging" type but aren't motorcyclist lodging — drop
# them so they don't crowd out real motels/hotels/inns (e.g. a KOA outranking a
# classic hotel). Keeps hotels, motels, inns, B&Bs, cottages, guest houses.
LODGING_EXCLUDE_TYPES = ["campground", "rv_park", "mobile_home_park"]


def _api_key() -> str:
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY not set (see .env)")
    return key


def geocode(town: str) -> tuple[float, float, str]:
    """Town name -> (lat, lon, display_name) via OpenStreetMap Nominatim."""
    resp = httpx.get(
        NOMINATIM_URL,
        params={"q": town, "format": "json", "limit": 1, "countrycodes": "us"},
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    hits = resp.json()
    if not hits:
        raise RuntimeError(f"Could not geocode '{town}'. Try a more specific name.")
    h = hits[0]
    return float(h["lat"]), float(h["lon"]), h.get("display_name", town)


def search_nearby(
    lat: float,
    lon: float,
    included_types: list[str],
    radius_m: float = 10000.0,
    max_results: int = 20,
    excluded_types: list[str] | None = None,
) -> list[dict]:
    """Cheap Nearby Search. Returns lightweight candidate dicts.

    Field mask is deliberately minimal (id/name/rating/count/type/location) so
    this stays on the cheap SKU; richer fields come from place_details() on the
    survivors only.
    """
    field_mask = ",".join(
        [
            "places.id",
            "places.displayName",
            "places.rating",
            "places.userRatingCount",
            "places.primaryType",
            "places.types",
            "places.formattedAddress",
            "places.location",
        ]
    )
    body = {
        "includedTypes": included_types,
        "maxResultCount": max_results,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": radius_m,
            }
        },
    }
    if excluded_types:
        body["excludedTypes"] = excluded_types
    resp = httpx.post(
        f"{PLACES_BASE}/places:searchNearby",
        headers={
            "X-Goog-Api-Key": _api_key(),
            "X-Goog-FieldMask": field_mask,
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    out = []
    for p in resp.json().get("places", []):
        out.append(
            {
                "id": p.get("id"),
                "name": (p.get("displayName") or {}).get("text", ""),
                "rating": p.get("rating"),
                "reviews": p.get("userRatingCount"),
                "primary_type": p.get("primaryType"),
                "types": p.get("types", []),
                "address": p.get("formattedAddress"),
                "lat": (p.get("location") or {}).get("latitude"),
                "lon": (p.get("location") or {}).get("longitude"),
            }
        )
    return out


def place_details(place_id: str) -> dict:
    """Richer details for a survivor: website, reviews, editorial summary, photos."""
    field_mask = ",".join(
        [
            "id",
            "displayName",
            "rating",
            "userRatingCount",
            "primaryType",
            "websiteUri",
            "googleMapsUri",
            "editorialSummary",
            "reviews",
            "photos",
        ]
    )
    resp = httpx.get(
        f"{PLACES_BASE}/places/{place_id}",
        headers={
            "X-Goog-Api-Key": _api_key(),
            "X-Goog-FieldMask": field_mask,
        },
        timeout=30,
    )
    resp.raise_for_status()
    p = resp.json()
    reviews = []
    for r in p.get("reviews", [])[:5]:
        txt = (r.get("text") or {}).get("text") or (r.get("originalText") or {}).get("text", "")
        reviews.append({"rating": r.get("rating"), "text": txt})
    return {
        "id": p.get("id"),
        "name": (p.get("displayName") or {}).get("text", ""),
        "rating": p.get("rating"),
        "reviews_count": p.get("userRatingCount"),
        "primary_type": p.get("primaryType"),
        "website": p.get("websiteUri"),
        "maps_uri": p.get("googleMapsUri"),
        "summary": (p.get("editorialSummary") or {}).get("text"),
        "photo_count": len(p.get("photos", [])),
        "reviews": reviews,
    }


def streetview_link(lat: float, lon: float) -> str:
    """A Street View URL the user can click to make the final visual call."""
    return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
