"""Phase 1 bare loop: town in -> verdict out. No DB.

    uv run python verdict.py "Stanley, ID"

Pipeline: geocode -> cheap Places Nearby Search (lodging + food) -> chain
blocklist filter -> Place Details on survivors -> ONE Bedrock judgment call ->
printed verdict. The whole point of Phase 1 is to tune the prompt + blocklist
against towns where the answer is already known.
"""

from __future__ import annotations

import json
import os
import sys

import boto3
from dotenv import load_dotenv

import places
from chains import filter_independents

load_dotenv(override=True)  # .env is the source of truth (e.g. AWS_PROFILE)

MODEL_ID = os.environ.get("STRANDS_PG_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
# How many survivors (by rating) to pull details for and judge, per category.
TOP_N_LODGING = 6
TOP_N_FOOD = 8

SYSTEM_PROMPT = """\
You are a scout for a motorcyclist deciding whether a TOWN is worth stopping in to sleep and
eat. Score the town 0-10 using its BEST independent lodging plus the town's food scene, then
assign a band. Output ONLY JSON in the schema at the end.

The unit is the TOWN. Pick the single best independent lodging option from the candidates as
the town's place to sleep, and score the lodging dimensions on it. Score food on the town's
independent food candidates. Great lodging in a town with no real food is not a high score,
and vice versa.

== SCORING RUBRIC (sum the points to 0-10) ==

LODGING (5 pts), scored on the best independent lodging:
- independence_character (0-2): 2 = clearly independent, character evident in reviews (named
  owner, specific decor, personality-driven praise); 1 = independent but generic execution,
  OR a soft-brand-affiliated independent (Ascend, Tapestry, Tribute Portfolio, Curio,
  Autograph, Unbound — own identity, chain booking system); 0 = a real chain.
- price_tier (0-1.5): 1.5 = no price-apologetics (price unmentioned, or a pleasant surprise
  for the value); 0.75 = mixed; 0 = price-as-apology dominant ("decent for the money", "you
  can pay more for better", "budget option but").
- review_quality (0-1.5): 1.5 = specific, sensory, repeat-visit; complaints (if any) specific
  and offset by specific praise; 1.0 = positive but generic; 0.5 = real praise alongside real
  clustered complaints (legit "good but uneven" — do NOT auto-fail); 0 = thin, generic, or a
  dominant complaint pattern.

FOOD (3 pts):
- food_proximity_quality (0-2): 2 = non-chain restaurant within walking distance, specifically
  NAMED in the lodging reviews; 1.5 = good food nearby, mentioned but not named; 1.0 = food
  exists but not mentioned in lodging reviews; 0 = chain-only or dead food scene.
- food_recency (0-1): 1.0 = strong reviews within ~18 months; 0.5 = older/mixed; 0 = no recent
  signal or signs of closure. (Each review carries `when`, e.g. "4 months ago".)

TOWN FIT (2 pts):
- leisure_vs_workforce (0-1): 1 = through-travelers/recreationists/road-trippers/repeat
  leisure visitors dominate; 0.5 = mixed; 0 = workforce/industrial dominant, weekly-rate
  pattern common in the ACTUAL reviews.
- riding_context (0-1): 1 = on/near good riding, or reviews mention riding/outdoor recreation
  unprompted; 0.5 = general outdoor/tourism, no specific riding signal; 0 = pure transit or
  freight town.

band: total >= 8 "route-worthy"; 6-7.99 "acceptable"; 4-5.99 "marginal"; < 4 "filter-out".

== HOW TO READ REVIEWS (stance, not keywords) ==
1. PRICE-AS-APOLOGY vs PRICE-AS-VALUE: "you can pay more for better" = apology (penalize);
   "best stay for the price, full stop" = value (reward). Same words, opposite stance.
2. PREPONDERANCE OVER OUTLIERS: one oddly-flavored review (e.g. a business traveler) does not
   override a cluster of consistent, specific, repeat-visit positives.
3. WEEKLY-RATE CONTEXT: "offers weekly rates" alone is not a red flag; "week-to-week living is
   the DOMINANT pattern in the actual reviews" is.
4. FOOD PROXIMITY CORROBORATES THE BLOCK: a specifically-named, loved restaurant in a
   lodging's own reviews is evidence about the area's character, not just dinner.
5. COMPETENT BEATS NOTHING: a well-run, clean place in a real town with good food nearby
   scores well even without an owner-personality angle. Don't only reward the most charming.
6. GOOD-BUT-UNEVEN IS A PASS: specific, varied complaints (noise, mid-renovation, a so-so
   sub-let restaurant) next to specific praise = an honest, real place. Surface it as an
   actionable `tip` ("ask for a room not over the bar"); do not penalize like generic gripes.

REVIEW SKEW: the <=5 reviews shown are Google's "most relevant" and skew POSITIVE; they
cannot be expanded. Anchor on the aggregate `rating` across all `reviews_count`. When the
shown reviews are all 4-5 stars but the aggregate is mediocre over many ratings, assume a
hidden negative tail and temper. Owner REPLIES to reviews are NOT in the data — judge
character from guest review text, not from owner responses.

== OUTPUT (JSON only, no prose) ==
{
  "best_lodging": {"name": "...", "soft_brand": false, "synthesis": "<=2 honest lines"},
  "food": [{"name": "...", "synthesis": "<=1 line"}],
  "scores": {
    "independence_character": 0, "price_tier": 0, "review_quality": 0,
    "food_proximity_quality": 0, "food_recency": 0,
    "leisure_vs_workforce": 0, "riding_context": 0
  },
  "total": 0.0,
  "band": "route-worthy|acceptable|marginal|filter-out",
  "reason": "one line",
  "tip": "one actionable line, or empty string"
}
"""


def _gather(lat, lon, included_types, top_n, excluded_types=None):
    """Cheap search -> chain filter -> details on top survivors. Returns
    (survivors_with_details, dropped_chains)."""
    candidates = places.search_nearby(lat, lon, included_types, excluded_types=excluded_types)
    keep, dropped = filter_independents(candidates)
    # Rank survivors by rating (then review count) and pull details on the best few.
    keep.sort(key=lambda c: ((c.get("rating") or 0), (c.get("reviews") or 0)), reverse=True)
    detailed = []
    for c in keep[:top_n]:
        try:
            d = places.place_details(c["id"])
        except Exception as exc:  # noqa: BLE001 - details are best-effort
            d = {"name": c["name"], "rating": c.get("rating"), "error": str(exc)}
        d["lat"], d["lon"] = c.get("lat"), c.get("lon")
        detailed.append(d)
    return detailed, dropped


def _judge(town: str, lodging: list[dict], food: list[dict]) -> dict:
    payload = {
        "town": town,
        "lodging_candidates": [_slim(p) for p in lodging],
        "food_candidates": [_slim(p) for p in food],
    }
    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    resp = client.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": json.dumps(payload, indent=2)}]}],
        inferenceConfig={"maxTokens": 2000, "temperature": 0.2},
    )
    text = resp["output"]["message"]["content"][0]["text"].strip()
    # Models sometimes wrap JSON in ```; strip a fence if present.
    if text.startswith("```"):
        text = text.split("```", 2)[1].lstrip("json").strip()
    return json.loads(text)


def _slim(p: dict) -> dict:
    """Only the fields the model should judge on."""
    return {
        "name": p.get("name"),
        "rating": p.get("rating"),
        "reviews_count": p.get("reviews_count"),
        "primary_type": p.get("primary_type"),
        "summary": p.get("summary"),
        "website": p.get("website"),
        "reviews": [
            {"stars": r.get("rating"), "when": r.get("when"), "text": r.get("text")}
            for r in p.get("reviews", [])
            if r.get("text")
        ][:5],
    }


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: python verdict.py "Town, ST"')
        return 2
    town = sys.argv[1]

    lat, lon, display = places.geocode(town)
    print(f"\n=== {town} ===")
    print(f"geocoded: {display}  ({lat:.4f}, {lon:.4f})\n")

    lodging, lodging_chains = _gather(
        lat, lon, places.LODGING_TYPES, TOP_N_LODGING, excluded_types=places.LODGING_EXCLUDE_TYPES
    )
    food, food_chains = _gather(lat, lon, places.FOOD_TYPES, TOP_N_FOOD)

    print(f"lodging: {len(lodging)} independent survivors "
          f"({len(lodging_chains)} chains dropped: {_names(lodging_chains)})")
    print(f"food:    {len(food)} independent survivors "
          f"({len(food_chains)} chains dropped: {_names(food_chains)})\n")

    if not lodging and not food:
        print("SCORE: 0/10  [filter-out] — no independent lodging or food found.\n")
        return 0

    r = _judge(town, lodging, food)
    _print_score(r, lodging)
    return 0


def _names(items: list[dict]) -> str:
    return ", ".join(i.get("name", "?") for i in items) or "none"


def _print_score(r: dict, lodging: list[dict]) -> None:
    s = r.get("scores", {})

    def g(k):
        return s.get(k, 0)

    print(f"SCORE: {r.get('total')}/10  [{r.get('band')}] — {r.get('reason')}\n")
    print(f"  lodging  | indep/char {g('independence_character')}/2  "
          f"price {g('price_tier')}/1.5  reviews {g('review_quality')}/1.5")
    print(f"  food     | proximity {g('food_proximity_quality')}/2  "
          f"recency {g('food_recency')}/1")
    print(f"  town fit | leisure {g('leisure_vs_workforce')}/1  "
          f"riding {g('riding_context')}/1\n")

    bl = r.get("best_lodging") or {}
    detail = next((d for d in lodging if d.get("name") == bl.get("name")), {})
    soft = " (soft-brand)" if bl.get("soft_brand") else ""
    rating, rc = detail.get("rating"), detail.get("reviews_count")
    print(f"BEST LODGING: {bl.get('name')}{soft}  ({rating}★ / {rc} reviews)")
    print(f"  {bl.get('synthesis')}")
    if detail.get("website"):
        print(f"  web: {detail['website']}")
    if detail.get("lat"):
        print(f"  streetview: {places.streetview_link(detail['lat'], detail['lon'])}")

    print("\nFOOD:")
    for f in r.get("food", []):
        print(f"  - {f.get('name')}: {f.get('synthesis')}")

    if r.get("tip"):
        print(f"\nTIP: {r['tip']}")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
