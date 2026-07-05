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
The rider is on a MOTORCYCLE. Ideal lodging is an independent MOTEL or a classic independent
HOTEL / lodge / inn. A bed & breakfast, guest house, private room, or single-cabin rental is
NOT typical moto-trip lodging — see the B&B rule.

LODGING (4 pts), scored on the best SUITABLE independent lodging:
- independence_character (0-2): 2 = clearly independent motel/hotel/inn, character evident in
  reviews (named owner, specific decor, personality-driven praise); 1 = independent but generic
  execution, OR soft-brand-affiliated (Ascend, Tapestry, Tribute Portfolio, Curio, Autograph,
  Unbound); 0 = a real chain. B&B RULE — SELECTION FIRST: pick the best SUITABLE option (motel
  / hotel / lodge / inn) as the town's representative EVEN IF a bed_and_breakfast / guest_house
  / private room / single cabin is higher-rated — the rider books the motel, not the B&B (note
  the B&B as an alternative if you like). Only when the town has NO suitable motel/hotel/inn
  worth a look do you fall back to a B&B, and then CAP this at 0.75 and say so — a B&B-only town
  cannot be route-worthy on lodging.
- price_tier (0-1): 1 = no price-apologetics; 0.5 = mixed; 0 = price-as-apology dominant
  ("decent for the money", "you can pay more for better", "budget option but").
- review_quality (0-1): 1 = specific, sensory, repeat-visit, complaints (if any) specific and
  offset by specific praise; 0.5 = positive-but-generic OR good-but-uneven (real praise beside
  real clustered complaints — do NOT auto-fail); 0 = thin, generic, or dominant complaints.

FOOD (3 pts):
- food_proximity_quality (0-2): judge a rider arriving in the EVENING for DINNER, and separate
  a genuine food DESTINATION from "you'll eat fine".
  2 = a real non-chain STANDOUT worth planning around. Operational bar: the town's best
    non-chain dinner spot rates ~4.7+ with real volume, or is unmistakably raved about as a
    destination. Review COUNT alone does NOT qualify — a small town funnels all its reviews to
    the one main spot, so a popular bar & grill at 4.4-4.6 is NOT a destination no matter how
    many reviews it has.
  1.5 = solid, adequate real dinner options (a bar & grill / Mexican / diner / BBQ, typically
    topping out around 4.4-4.6) — you'll eat fine, but nothing destination-worthy. This is the
    DEFAULT for a normal small town with real restaurants.
  1.0 = LIMITED — the non-chain scene is mostly coffee / bakery / ice-cream / deli or daytime-
    only spots, or a single weak option.
  0 = chain-only or a dead food scene.
  A creamery, coffee roaster, or a mid-afternoon bakery does NOT by itself earn a high score;
  weigh place types, review volume/enthusiasm, and any review mentions of hours.
- food_recency (0-1): 1 = strong reviews within ~18 months; 0.5 = older/mixed; 0 = no recent
  signal or signs of closure. (Each review carries `when`, e.g. "4 months ago".)

TOWN (3 pts):
- town_charm (0-2): the town's character as a place to spend an evening. 2 = charming — a
  walkable historic downtown, a real arts/festival culture, or a genuine recreation destination
  (weigh the `town_attractions` list, YOUR OWN knowledge of the town, and review mentions of
  "historic downtown / main street / festival"). 1 = some draw but ordinary. 0 = workforce /
  industrial / transit town with no real center. A single famous roadside oddity (a big
  sculpture, one museum) does NOT make a workforce town charming — weigh KIND, not count.
- riding_context (0-1): 1 = on/near good riding, or reviews mention riding/outdoor recreation
  unprompted; 0.5 = general outdoor/tourism; 0 = pure transit or freight town.

band: total >= 8 "route-worthy"; 6-7.99 "acceptable"; 4-5.99 "marginal"; < 4 "filter-out".

LODGING GATE (this tool finds places to SLEEP and eat): if the town has NO suitable rider
lodging at all — no motel / hotel / inn / lodge worth a look, only vacation rentals, private
lofts, or nothing bookable for a one-night stop — the town is NOT an overnight candidate. Set
all three lodging scores to 0, cap the TOTAL at 1.5, band "filter-out", and say in the reason
that it's a dinner/charm stop only, not a place to sleep. Great food or charm does NOT rescue a
town with nowhere to sleep. (A merely weak or B&B-only lodging still counts as lodging — the
gate is only for NO bookable rider lodging.)

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

== CALIBRATION ANCHORS (dimensions on the NEW weights; downgrades are where discrimination
lives — do NOT give every town top marks) ==
- Mountain Spirit Inn, Darby MT ~= 9.5 (route-worthy). Owner-personality inn, sensory
  repeat-visit praise; named loved food nearby; recreation town.
  indep 2 / price 1 / reviews 1 / food 2 / recency 1 / charm 1.5 / riding 1.
- Covered Wagon Motel, Lusk WY ~= 7.5 (acceptable). Strong independent motel; town food thin
  (one sit-down + a Subway) -> food 1; small ranch/festival town -> charm 1; riding 0.5.
  indep 2 / price 1 / reviews 1 / food 1 / recency 1 / charm 1 / riding 0.5.
- Georgetown Mountain Inn, Georgetown CO ~= 8.0 (route-worthy). COMPETENT-BUT-GENERIC motel
  (generic praise, minor gripes) -> indep 1.5, reviews 0.5; but a genuinely charming preserved
  Victorian mining town -> charm 2; named food nearby -> food 2.
  indep 1.5 / price 1 / reviews 0.5 / food 2 / recency 1 / charm 2 / riding 1.
- Hotel Seville, Harrison AR ~= 6.0 (acceptable). GOOD-BUT-UNEVEN hotel, soft-brand -> indep 1;
  clustered specific complaints (room over the bar, water shut off, thin walls) -> reviews 0.5;
  faintly price-apologetic -> price 0.5; Ozark/Branson-gateway tourism -> charm 1. TIP: "ask
  for a room not over the bar". indep 1 / price 0.5 / reviews 0.5 / food 1.5 / recency 1 /
  charm 1 / riding 0.5.
- 1st Inn Alliance, Alliance NE ~= 2.0 (FILTER-OUT). PRICE-AS-APOLOGY dominant -> price 0;
  thin/generic -> reviews 0.5; independent but zero charm, week-to-week feel -> indep 0.5;
  railroad/workforce town, Carhenge is an isolated roadside oddity -> charm 0, riding 0; weak
  food -> food 0.5. indep 0.5 / price 0 / reviews 0.5 / food 0.5 / recency 0.5 / charm 0 / riding 0.

SHARPENING:
- Top lodging marks are the exception. Generic praise or clustered complaints CANNOT earn full
  review_quality. A B&B as the best option caps independence_character at 0.75 (B&B RULE).
- For town_charm, use your own knowledge of the town's economy: railroad division points,
  oil/gas/fracking hubs, prison towns, and meatpacking/factory/ag-processing centers are
  workforce towns (charm 0-1) even with one famous attraction.

== OUTPUT (JSON only, no prose) ==
Every dimension needs a `notes` entry: a specific one-line WHY for that score, citing
the concrete signal (a named place, a review detail, the town's economy, the best dinner
spot's rating) — not a restatement of the rubric. This is the explanation the user reads.
{
  "best_lodging": {"name": "...", "soft_brand": false, "synthesis": "<=2 honest lines"},
  "food": [{"name": "...", "synthesis": "<=1 line"}],
  "scores": {
    "independence_character": 0, "price_tier": 0, "review_quality": 0,
    "food_proximity_quality": 0, "food_recency": 0,
    "town_charm": 0, "riding_context": 0
  },
  "notes": {
    "independence_character": "<=16 words, concrete", "price_tier": "...",
    "review_quality": "...", "food_proximity_quality": "...", "food_recency": "...",
    "town_charm": "...", "riding_context": "..."
  },
  "total": 0.0,
  "band": "route-worthy|acceptable|marginal|filter-out",
  "reason": "one line",
  "tip": "one actionable line, or empty string"
}
"""


def _gather(lat, lon, included_types, top_n, excluded_types=None, keep_here=None):
    """Cheap search -> nearest-town filter -> chain filter -> details on top
    survivors. Returns (survivors_with_details, dropped_chains).

    keep_here(vlat, vlon) -> bool, when given, keeps only venues whose nearest
    reference town is this one, so neighbours don't borrow each other's venues.
    """
    candidates = places.search_nearby(lat, lon, included_types, excluded_types=excluded_types)
    if keep_here is not None:
        candidates = [c for c in candidates
                      if c.get("lat") is None or keep_here(c["lat"], c["lon"])]
    keep, dropped = filter_independents(candidates)
    # Rank survivors by a volume-weighted rating (a tiny-sample gem shouldn't bury
    # a high-review classic) and pull details on the best few.
    keep.sort(
        key=lambda c: (
            places.weighted_rating(c.get("rating"), c.get("reviews")),
            (c.get("reviews") or 0),
        ),
        reverse=True,
    )
    detailed = []
    for c in keep[:top_n]:
        try:
            d = places.place_details(c["id"])
        except Exception as exc:  # noqa: BLE001 - details are best-effort
            d = {"name": c["name"], "rating": c.get("rating"), "error": str(exc)}
        d["lat"], d["lon"] = c.get("lat"), c.get("lon")
        detailed.append(d)
    return detailed, dropped


def _judge(
    town: str, lodging: list[dict], food: list[dict], attractions: list[dict], mode: str = "moto"
) -> dict:
    payload = {
        "town": town,
        "lodging_candidates": [_slim(p) for p in lodging],
        "food_candidates": [_slim(p) for p in food],
        "town_attractions": [
            {"name": a.get("name"), "type": a.get("primary_type"), "reviews": a.get("reviews")}
            for a in attractions
        ],
    }
    if mode == "couple":
        mode_note = (
            "\n\nTRIP MODE = couple/car: bed & breakfasts and guest houses ARE acceptable "
            "lodging — do NOT apply the B&B cap; score a good B&B like any independent lodging "
            "(character is often a plus)."
        )
    else:
        mode_note = (
            "\n\nTRIP MODE = moto/group: B&Bs and guest houses are excluded upstream (a group of "
            "riders won't book one). If one still appears, treat it as unsuitable lodging."
        )
    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    resp = client.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT + mode_note}],
        messages=[{"role": "user", "content": [{"text": json.dumps(payload, indent=2)}]}],
        inferenceConfig={"maxTokens": 2000, "temperature": 0.2},
    )
    text = resp["output"]["message"]["content"][0]["text"].strip()
    # Models sometimes wrap JSON in ```; strip a fence if present.
    if text.startswith("```"):
        text = text.split("```", 2)[1].lstrip("json").strip()
    r = json.loads(text)
    return _apply_lodging_gate(r)


def _apply_lodging_gate(r: dict) -> dict:
    """No bookable rider lodging => the town can't be an overnight stop. Cap it
    near-zero regardless of how good the food/charm are (deterministic backstop
    to the prompt's LODGING GATE)."""
    s = r.get("scores", {})
    lodging = sum(s.get(k) or 0 for k in ("independence_character", "price_tier", "review_quality"))
    if lodging == 0 and (r.get("total") or 0) > 1.5:
        r["total"] = 1.5
        r["band"] = "filter-out"
        r["reason"] = "No place to sleep (no rider lodging) — dinner/charm stop only. " + (
            r.get("reason") or ""
        )
    return r


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
    argv = sys.argv[1:]
    flags = {a for a in argv if a.startswith("--")}
    positional = [a for a in argv if not a.startswith("--")]
    if not positional:
        print('usage: python verdict.py "Town, ST" [--couple]')
        return 2
    town = positional[0]
    mode = "couple" if ({"--couple", "--car"} & flags) else "moto"

    lat, lon, display = places.geocode(town)
    print(f"\n=== {town} ===   [mode: {mode}]")
    print(f"geocoded: {display}  ({lat:.4f}, {lon:.4f})\n")

    lodging_types = list(places.LODGING_TYPES)
    lodging_excl = list(places.LODGING_EXCLUDE_TYPES)
    if mode == "moto":
        # Drop B&B types from BOTH included and excluded-conflict: a type can't be
        # in includedTypes and excludedTypes at once (400).
        lodging_types = [t for t in lodging_types if t not in places.LODGING_BNB_TYPES]
        lodging_excl += places.LODGING_BNB_TYPES
    lodging, lodging_chains = _gather(
        lat, lon, lodging_types, TOP_N_LODGING, excluded_types=lodging_excl
    )
    food, food_chains = _gather(lat, lon, places.FOOD_TYPES, TOP_N_FOOD)
    attractions = places.search_nearby(
        lat, lon, places.ATTRACTION_TYPES, radius_m=8000.0, max_results=15
    )

    print(f"lodging: {len(lodging)} independent survivors "
          f"({len(lodging_chains)} chains dropped: {_names(lodging_chains)})")
    print(f"food:    {len(food)} independent survivors "
          f"({len(food_chains)} chains dropped: {_names(food_chains)})")
    print(f"charm:   {len(attractions)} nearby attractions/cultural sites\n")

    if not lodging and not food:
        print("SCORE: 0/10  [filter-out] — no independent lodging or food found.\n")
        return 0

    r = _judge(town, lodging, food, attractions, mode)
    _print_score(r, lodging)
    return 0


def _names(items: list[dict]) -> str:
    return ", ".join(i.get("name", "?") for i in items) or "none"


def _print_score(r: dict, lodging: list[dict]) -> None:
    s = r.get("scores", {})

    def g(k):
        return s.get(k, 0)

    print(f"SCORE: {r.get('total')}/10  [{r.get('band')}] — {r.get('reason')}\n")
    print(f"  lodging | indep/char {g('independence_character')}/2  "
          f"price {g('price_tier')}/1  reviews {g('review_quality')}/1")
    print(f"  food    | proximity {g('food_proximity_quality')}/2  "
          f"recency {g('food_recency')}/1")
    print(f"  town    | charm {g('town_charm')}/2  "
          f"riding {g('riding_context')}/1")
    notes = r.get("notes") or {}
    if notes:
        labels = {
            "independence_character": "indep", "price_tier": "price", "review_quality": "reviews",
            "food_proximity_quality": "food", "food_recency": "recency",
            "town_charm": "charm", "riding_context": "riding",
        }
        print("  why:")
        for k, lbl in labels.items():
            if notes.get(k):
                print(f"    {lbl:>7} {g(k)} — {notes[k]}")
    print()

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
