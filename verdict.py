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
You are a scout for a motorcyclist who wants to sleep and eat well in small towns.
You judge whether a TOWN is worth stopping in. A town only passes if it has BOTH:
  - at least one independent, clean, my-kind-of-place motel/inn worth a look, AND
  - at least one good non-chain place to eat.

How to judge (small-town aware):
- Prefer independent, owner-run places with character over polished resort/chain feel.
- The AGGREGATE rating is your primary signal. Do NOT impose a hard review-count floor: a
  genuine gem in a 200-person town may have only 20-40 reviews. Use review count as a
  tiebreaker, not a gate. Be MORE forgiving on food review counts than on lodging.
- REVIEW SKEW (important): the `reviews` shown are at most 5 and are Google's "most
  relevant" — they skew POSITIVE and cannot be sorted or expanded. They are NOT the full
  picture. Each shown review carries its own `stars`, so compare them to the aggregate: when
  the shown reviews are all 4-5 stars but the aggregate `rating` is mediocre (<= ~4.2) over
  many ratings, assume a real negative tail you cannot see and TEMPER the synthesis.
- Still mine the shown reviews for concrete negatives (bedbugs, smell, rude owner, road
  noise, "tired"/"dated" done badly) and surface them — but the absence of negatives in a
  rosy 5-review sample is NOT evidence a place is clean.
- Some chains may have slipped past the upstream filter. If a place is clearly a chain,
  flag it independent=false and do not count it toward the town passing.

Return ONLY valid JSON, no prose, in exactly this shape:
{
  "lodging": [
    {"name": "...", "independent": true, "recommend": true, "synthesis": "<=2 honest lines incl. any negative"}
  ],
  "food": [
    {"name": "...", "independent": true, "recommend": true, "synthesis": "<=2 honest lines incl. any negative"}
  ],
  "town_verdict": "PASS" | "FAIL",
  "reason": "one line: why the town passes or fails"
}
"""


def _gather(lat: float, lon: float, included_types: list[str], top_n: int):
    """Cheap search -> chain filter -> details on top survivors. Returns
    (survivors_with_details, dropped_chains)."""
    candidates = places.search_nearby(lat, lon, included_types)
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
            {"stars": r.get("rating"), "text": r.get("text")}
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

    lodging, lodging_chains = _gather(lat, lon, places.LODGING_TYPES, TOP_N_LODGING)
    food, food_chains = _gather(lat, lon, places.FOOD_TYPES, TOP_N_FOOD)

    print(f"lodging: {len(lodging)} independent survivors "
          f"({len(lodging_chains)} chains dropped: {_names(lodging_chains)})")
    print(f"food:    {len(food)} independent survivors "
          f"({len(food_chains)} chains dropped: {_names(food_chains)})\n")

    if not lodging and not food:
        print("VERDICT: FAIL — no independent lodging or food found.\n")
        return 0

    verdict = _judge(town, lodging, food)

    print(f"VERDICT: {verdict.get('town_verdict')} — {verdict.get('reason')}\n")
    _print_section("LODGING", verdict.get("lodging", []), lodging)
    _print_section("FOOD", verdict.get("food", []), food)
    return 0


def _names(items: list[dict]) -> str:
    return ", ".join(i.get("name", "?") for i in items) or "none"


def _print_section(label: str, judged: list[dict], detailed: list[dict]) -> None:
    by_name = {d.get("name"): d for d in detailed}
    print(f"-- {label} --")
    for j in judged:
        flag = "✓" if j.get("recommend") else " "
        indie = "indie" if j.get("independent") else "CHAIN?"
        d = by_name.get(j.get("name"), {})
        rating = d.get("rating")
        rc = d.get("reviews_count")
        sv = places.streetview_link(d["lat"], d["lon"]) if d.get("lat") else ""
        print(f"  [{flag}] {j.get('name')}  ({rating}★ / {rc} reviews, {indie})")
        print(f"      {j.get('synthesis')}")
        if d.get("website"):
            print(f"      web: {d['website']}")
        if sv:
            print(f"      streetview: {sv}")
    if not judged:
        print("  (none)")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
