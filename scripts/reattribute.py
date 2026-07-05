"""Re-score every cached verdict with nearest-town venue attribution.

    uv run python scripts/reattribute.py [--limit N] [--dry] [--min-drop X]

Verdicts scored before the attribution fix credited a town with any venue inside
its ~10km search circle, so satellites borrowed a big neighbour's lodging/food
(Sageville, IA scored 10.0 on Dubuque's hotels). This re-scores each cached
(town, mode) with anchors = reference towns within ANCHOR_MI, so every venue
counts only for its nearest town. In-place upsert; idempotent.

--dry lists the work and spends nothing. --min-drop X only prints rows whose
total moved by >= X (spot the big corrections). Run on the LXC after deploy:
    docker compose exec agent python scripts/reattribute.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import area/cache

from dotenv import load_dotenv

import area
import cache

load_dotenv(override=True)

# Anchor radius: venues are found within ~6.2 mi of a town, so the true nearest
# town to any of them is within ~12.4 mi. 15 mi covers that with margin.
ANCHOR_MI = 15.0


def cached_verdicts(conn):
    """Every stored verdict: (town, state, geoid, mode, lat, lon, total)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT town, state, geoid, mode, lat, lon, total "
            "FROM town_verdicts ORDER BY total DESC NULLS LAST"
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def main() -> int:
    argv = sys.argv[1:]
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    dry = "--dry" in argv
    min_drop = float(argv[argv.index("--min-drop") + 1]) if "--min-drop" in argv else 0.0

    conn = cache.connect()
    rows = cached_verdicts(conn)
    if limit:
        rows = rows[:limit]
    print(f"{len(rows)} cached verdicts to re-attribute (anchor radius {ANCHOR_MI:.0f} mi)"
          f"{' — dry run' if dry else ''}\n")

    done = failed = moved = 0
    for t in rows:
        label = f"{t['town']}, {t['state']} [{t['mode']}]"
        if dry:
            print(f"  [would] {label:<30} was {t['total']}")
            done += 1
            continue
        try:
            anchors = [(a["name"], a["lat"], a["lon"])
                       for a in cache.towns_within(conn, t["lat"], t["lon"], ANCHOR_MI)]
            r = area.score_town(t["town"], t["lat"], t["lon"], t["mode"], anchors=anchors)
            cache.store_verdict(conn, t["town"], t["state"], t["geoid"], t["mode"],
                                t["lat"], t["lon"], r)
        except Exception as e:  # transient Places/Bedrock errors shouldn't kill the run
            print(f"  [ERROR] {label:<30} {type(e).__name__}: {str(e)[:70]} — skipping")
            conn.rollback()
            failed += 1
            continue
        old, new = t["total"], r.get("total")
        delta = (old or 0) - (new or 0)
        if abs(delta) >= 0.01:
            moved += 1
        if abs(delta) >= min_drop:
            flag = "  <== " if abs(delta) >= 2 else ""
            print(f"  [score] {label:<30} {old} -> {new}/10  {r.get('band')}{flag}")
        done += 1

    conn.close()
    print(f"\n{'would re-score' if dry else 're-scored'}: {done}   "
          f"changed: {moved}   failed: {failed}")
    print("(re-run to retry failures — idempotent)" if failed else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
