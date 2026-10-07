"""Postgres access for the verdict cache + town enumeration (host-side).

Towns come from the `towns` reference table (Census) via PostGIS ST_DWithin, so
an "area" needs no hand-seeded list. Verdicts are cached in `town_verdicts`
keyed by (town, state, mode); failures are stored too. Stale rows (> ttl) miss.
"""

from __future__ import annotations

import os

import psycopg
from psycopg.types.json import Jsonb

DSN = os.environ.get("STRANDS_PG_DSN", "postgresql://strands:strands@localhost:5433/strands")

# Place Details older than this are refetched (reviews/hours drift slowly).
PLACE_DETAILS_TTL_DAYS = int(os.environ.get("PLACE_DETAILS_TTL_DAYS", "90"))

# Census LSAD codes worth treating as real trip towns: city / town / village.
TOWN_LSADS = ("25", "43", "47")


def connect():
    return psycopg.connect(DSN)


def towns_within(conn, lat, lon, radius_mi, lsads=TOWN_LSADS):
    """Reference towns within radius_mi of (lat, lon), nearest first."""
    sql = """
        SELECT geoid, name, state, lat, lon,
               ST_Distance(location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)
               / 1609.344 AS mi
        FROM towns
        WHERE ST_DWithin(location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
          AND lsad = ANY(%s)
        ORDER BY mi
    """
    with conn.cursor() as cur:
        cur.execute(sql, [lon, lat, lon, lat, radius_mi * 1609.344, list(lsads)])
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def get_cached(conn, town, state, mode, ttl_days=180):
    """Fresh cached verdict for (town, state, mode), or None."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT total, band, scores, best_lodging, food, reason, tip, evaluated_at
            FROM town_verdicts
            WHERE town = %s AND state = %s AND mode = %s
              AND evaluated_at > now() - make_interval(days => %s)
            """,
            [town, state, mode, ttl_days],
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d.name for d in cur.description]
        return dict(zip(cols, row, strict=True))


def store_verdict(conn, town, state, geoid, mode, lat, lon, r):
    """Upsert a verdict (one current row per town+mode). Stores failures too."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO town_verdicts
                (town, state, geoid, mode, lat, lon, location,
                 total, band, scores, notes, best_lodging, food, reason, tip, verdict, evaluated_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                 %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (town, state, mode) DO UPDATE SET
                geoid = EXCLUDED.geoid, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
                location = EXCLUDED.location, total = EXCLUDED.total, band = EXCLUDED.band,
                scores = EXCLUDED.scores, notes = EXCLUDED.notes,
                best_lodging = EXCLUDED.best_lodging, food = EXCLUDED.food,
                reason = EXCLUDED.reason, tip = EXCLUDED.tip,
                verdict = EXCLUDED.verdict, evaluated_at = now()
            """,
            [
                town, state, geoid, mode, lat, lon, lon, lat,
                r.get("total"), r.get("band"), Jsonb(r.get("scores")), Jsonb(r.get("notes")),
                Jsonb(r.get("best_lodging")), Jsonb(r.get("food")),
                r.get("reason"), r.get("tip"), Jsonb(r),
            ],
        )
    conn.commit()


# Place Details cache. Each call opens its own short-lived connection because it
# runs in sweep pool threads, which must not share the worker's connection.

def get_place_details(place_id, ttl_days=None):
    """Fresh cached place_details() dict for place_id, or None."""
    ttl = PLACE_DETAILS_TTL_DAYS if ttl_days is None else ttl_days
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT data FROM place_details
               WHERE place_id = %s AND fetched_at > now() - make_interval(days => %s)""",
            [place_id, ttl],
        )
        row = cur.fetchone()
    return row[0] if row else None


def store_place_details(place_id, data):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO place_details (place_id, data, fetched_at) VALUES (%s, %s, now())
               ON CONFLICT (place_id) DO UPDATE SET data = EXCLUDED.data, fetched_at = now()""",
            [place_id, Jsonb(data)],
        )
