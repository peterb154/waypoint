"""Reject hunt — the 'can it say no?' half of calibration (issue #1).

Known-good agreement is 10/10, but the tool has never been observed to FAIL a
town. Truly-dead towns are rare, so we batch a corridor of small interstate
transit/workforce towns, score them, and rank by WEAKEST best-independent-
lodging. The data nominates the reject candidates; a human eyeballs the bottom
and confirms. Do NOT hand-pick towns you already believe are bad — that just
confirms a bias. Feed a real corridor and let the tail fall out.

    uv run python scripts/reject_hunt.py                 # default I-80 NE/WY batch
    uv run python scripts/reject_hunt.py "Town, ST" ...  # custom batch
    uv run python scripts/reject_hunt.py --couple        # couple/car mode

Ranks ascending by lodging sub-score (indep + price + reviews), then total, and
prints full detail for the weakest handful — the reject candidates to eyeball.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import places  # noqa: E402
from area import score_town  # noqa: E402

# A real I-80 corridor across Nebraska into Wyoming: a mix of tiny transit
# hamlets (Brady, Maxwell, Potter) and towns with genuine lodging (Ogallala,
# Sidney, Kimball). Not cherry-picked rejects — the point is to let the ranking
# surface the weak tail on its own.
DEFAULT_BATCH = [
    "Wood River, NE", "Shelton, NE", "Gibbon, NE", "Elm Creek, NE", "Overton, NE",
    "Lexington, NE", "Cozad, NE", "Gothenburg, NE", "Brady, NE", "Maxwell, NE",
    "Hershey, NE", "Sutherland, NE", "Paxton, NE", "Ogallala, NE", "Big Springs, NE",
    "Chappell, NE", "Sidney, NE", "Potter, NE", "Kimball, NE", "Pine Bluffs, WY",
]

LODGING_DIMS = ("independence_character", "price_tier", "review_quality")


def lodging_score(r: dict) -> float:
    s = r.get("scores") or {}
    return sum(s.get(k) or 0 for k in LODGING_DIMS)


def main() -> int:
    argv = sys.argv[1:]
    flags = {a for a in argv if a.startswith("--")}
    towns = [a for a in argv if not a.startswith("--")] or DEFAULT_BATCH
    mode = "couple" if ({"--couple", "--car"} & flags) else "moto"

    print(f"\n=== reject hunt: {len(towns)} towns  [mode: {mode}] ===")
    print("scoring (weakest best-lodging bubbles to the bottom)...\n")

    results = []
    for name in towns:
        try:
            lat, lon, _ = places.geocode(name)
            r = score_town(name, lat, lon, mode)
        except Exception as e:  # noqa: BLE001 - one bad town shouldn't sink the batch
            print(f"  ERROR  {name:<18} {e}")
            time.sleep(1)
            continue
        results.append((name, r))
        print(f"  scored {name:<18} lodging {lodging_score(r):.2f}/4   "
              f"total {r.get('total')}/10  [{r.get('band')}]")
        time.sleep(1)  # be polite to Nominatim

    ranked = sorted(results, key=lambda x: (lodging_score(x[1]), x[1].get("total") or 0))

    print("\n" + "=" * 74)
    print(f"RANKED BY WEAKEST BEST-LODGING  ({mode}) — reject candidates at the top")
    print("=" * 74)
    for name, r in ranked:
        bl = (r.get("best_lodging") or {})
        blname = bl.get("name") if isinstance(bl, dict) else None
        print(f"  lodging {lodging_score(r):.2f}/4  total {str(r.get('total')):>4}/10  "
              f"[{r.get('band'):<12}] {name:<18} {blname or '(no lodging)'}")

    # Detail on the weakest quarter (min 3) — the towns to eyeball for a FAIL.
    n_detail = max(3, len(ranked) // 4)
    print("\n" + "=" * 74)
    print(f"EYEBALL THESE {n_detail} — does the tool's 'no' match your gut?")
    print("=" * 74)
    for name, r in ranked[:n_detail]:
        _print_detail(name, r)
    return 0


def _print_detail(name: str, r: dict) -> None:
    bl = r.get("best_lodging") or {}
    s = r.get("scores") or {}
    notes = r.get("notes") or {}
    print(f"\n### {name}   {r.get('total')}/10  [{r.get('band')}]")
    print(f"    reason: {r.get('reason')}")
    print(f"    best lodging: {bl.get('name') or '(none)'} — {bl.get('synthesis') or ''}")
    for k in LODGING_DIMS:
        if notes.get(k):
            print(f"      {k}: {s.get(k)} — {notes[k]}")
    if r.get("tip"):
        print(f"    tip: {r['tip']}")


if __name__ == "__main__":
    raise SystemExit(main())
