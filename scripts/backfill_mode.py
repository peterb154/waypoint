"""Backfill verdicts from one trip mode to another by re-scoring existing towns.

    uv run python scripts/backfill_mode.py --from moto --to couple [--limit N] [--dry] [--refresh]

Every town already scored in --from mode is re-scored in --to mode (couple adds
B&Bs that moto excludes, and a nicer-food lean) and cached. Idempotent: a town
already scored fresh in --to mode is skipped unless --refresh. --dry lists the
work without spending any Places/Bedrock calls.

Run on the LXC after deploy:  docker compose exec agent \
    python scripts/backfill_mode.py --from moto --to couple
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import area/cache/places

from dotenv import load_dotenv

import area
import cache

load_dotenv(override=True)


def source_towns(conn, mode):
    """Distinct towns that have a verdict in `mode` (one row per town+mode)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT town, state, geoid, lat, lon FROM town_verdicts WHERE mode = %s",
            [mode],
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def main() -> int:
    argv = sys.argv[1:]
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    src = opt("--from", "moto")
    dst = opt("--to", "couple")
    limit = int(opt("--limit")) if "--limit" in argv else None
    dry = "--dry" in argv
    refresh = "--refresh" in argv

    conn = cache.connect()
    towns = source_towns(conn, src)
    if limit:
        towns = towns[:limit]
    print(f"{len(towns)} towns scored in '{src}' → backfilling '{dst}'"
          f"{' (dry run)' if dry else ''}\n")

    done = skipped = 0
    for t in towns:
        label = f"{t['town']}, {t['state']}"
        if not refresh and cache.get_cached(conn, t["town"], t["state"], dst):
            print(f"  [skip ] {label} (already {dst})")
            skipped += 1
            continue
        if dry:
            print(f"  [would] {label}")
            done += 1
            continue
        r = area.score_town(t["town"], t["lat"], t["lon"], dst)
        cache.store_verdict(conn, t["town"], t["state"], t["geoid"], dst,
                            t["lat"], t["lon"], r)
        print(f"  [score] {label:<24} {r.get('total')}/10  {r.get('band')}")
        done += 1

    conn.close()
    print(f"\n{'would score' if dry else 'scored'}: {done}   skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
