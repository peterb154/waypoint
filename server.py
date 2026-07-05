"""Minimal local server for the map: serves the UI, reads cached verdicts, and
runs area sweeps live (SSE). This is the seed of the deployable agent service —
the FastAPI /chat + tools + email get added on top for the LXC step.

    uv run uvicorn server:app --reload --port 8000
"""

from __future__ import annotations

import os
import threading
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import area
import cache

load_dotenv(override=True)

# Every sweep scores a town in BOTH trip modes, so all map views (moto/couple/
# lunch) populate from one sweep. Cached (town, mode) pairs are skipped.
SWEEP_MODES = ("moto", "couple")

app = FastAPI(title="waypoint")


@app.get("/api/health")
def health():
    """Liveness + which commit is deployed (surfaced by the deploy pipeline)."""
    return {"status": "ok", "commit": os.environ.get("GIT_SHA", "dev")}


@app.post("/api/deploy")
def deploy(authorization: str = Header(default="")):
    """Bearer-guarded: just touch the host trigger file; the host systemd .path
    unit does the actual git pull + rebuild (see deploy.sh). No docker.sock here."""
    token = os.environ.get("DEPLOY_TOKEN")
    if not token or authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="unauthorized")
    trigger = os.environ.get("DEPLOY_TRIGGER", "/opt/waypoint/.deploy-trigger")
    with open(trigger, "w") as f:
        f.write(str(int(time.time())))
    return {"status": "ok"}

_COLS = ("town, state, mode, lat, lon, total, band, scores, notes, best_lodging, food, "
         "reason, tip, evaluated_at")


@app.get("/api/verdicts")
def verdicts():
    """All cached verdicts with coords (feeds the map)."""
    conn = cache.connect()
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_COLS} FROM town_verdicts WHERE lat IS NOT NULL")
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/preview")
def preview(lat: float, lon: float, radius: float):
    """How many towns fall in the circle, and how many (town, mode) scoring calls
    still need doing — so a sweep's cost is known before enqueuing it. Both trip
    modes are scored, so `to_score` counts across moto + couple."""
    conn = cache.connect()
    towns = cache.towns_within(conn, lat, lon, radius)
    to_score = sum(
        1 for t in towns for m in SWEEP_MODES
        if not cache.get_cached(conn, t["name"], t["state"], m)
    )
    conn.close()
    return {"towns": len(towns), "to_score": to_score}


class SweepReq(BaseModel):
    lat: float
    lon: float
    radius: float


_JOB_COLS = ("id, lat, lon, radius_mi, mode, status, towns_total, towns_done, error, "
             "created_at, started_at, finished_at")


@app.post("/api/sweep_jobs")
def enqueue(req: SweepReq):
    """Queue an area to sweep. A background worker drains pending jobs FIFO."""
    conn = cache.connect()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sweep_jobs (lat, lon, radius_mi) VALUES (%s, %s, %s) RETURNING id",
            [req.lat, req.lon, req.radius],
        )
        job_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return {"id": job_id, "status": "pending"}


@app.get("/api/sweep_jobs")
def list_jobs():
    """Recent sweep jobs — feeds the backlog panel and the coverage layer."""
    conn = cache.connect()
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_JOB_COLS} FROM sweep_jobs ORDER BY created_at DESC LIMIT 50")
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    conn.close()
    return rows


@app.delete("/api/sweep_jobs/{job_id}")
def cancel_job(job_id: int):
    """Drop a job that hasn't started yet (running/done are left alone)."""
    conn = cache.connect()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sweep_jobs WHERE id = %s AND status = 'pending'", [job_id])
        deleted = cur.rowcount
    conn.commit()
    conn.close()
    return {"deleted": deleted}


# ---- background sweep worker (one daemon thread; single uvicorn worker) ----

def _claim_next(conn):
    """Atomically grab the oldest pending job and mark it running."""
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE sweep_jobs SET status = 'running', started_at = now()
               WHERE id = (SELECT id FROM sweep_jobs WHERE status = 'pending'
                           ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED)
               RETURNING id, lat, lon, radius_mi"""
        )
        return cur.fetchone()


def _run_job(conn, job_id, lat, lon, radius):
    towns = cache.towns_within(conn, lat, lon, radius)
    with conn.cursor() as cur:
        cur.execute("UPDATE sweep_jobs SET towns_total = %s WHERE id = %s", [len(towns), job_id])
    for i, t in enumerate(towns, 1):
        for mode in SWEEP_MODES:
            if cache.get_cached(conn, t["name"], t["state"], mode):
                continue
            try:
                r = area.score_town(t["name"], t["lat"], t["lon"], mode)
                cache.store_verdict(conn, t["name"], t["state"], t["geoid"], mode,
                                    t["lat"], t["lon"], r)
            except Exception as e:  # transient Places/Bedrock errors shouldn't kill the job
                print(f"[worker] job {job_id} {t['name']}, {t['state']} ({mode}): "
                      f"{type(e).__name__}: {str(e)[:80]} — skipping")
        with conn.cursor() as cur:
            cur.execute("UPDATE sweep_jobs SET towns_done = %s WHERE id = %s", [i, job_id])
    with conn.cursor() as cur:
        cur.execute("UPDATE sweep_jobs SET status = 'done', finished_at = now() WHERE id = %s",
                    [job_id])


def _worker_loop():
    conn = cache.connect()
    conn.autocommit = True
    # A container restart (e.g. a deploy) kills the worker mid-job, stranding that
    # job as 'running' forever. With a single worker, anything 'running' at boot is
    # such an orphan — re-queue it. Re-scoring is cheap: cached towns are skipped.
    with conn.cursor() as cur:
        cur.execute("UPDATE sweep_jobs SET status = 'pending', started_at = NULL, "
                    "towns_done = 0 WHERE status = 'running'")
        if cur.rowcount:
            print(f"[worker] re-queued {cur.rowcount} orphaned running job(s)")
    while True:
        job = None
        try:
            job = _claim_next(conn)
            if not job:
                time.sleep(2)
                continue
            _run_job(conn, *job)
        except Exception as e:  # keep the worker alive across unexpected failures
            print(f"[worker] error: {type(e).__name__}: {e}")
            if job:
                try:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE sweep_jobs SET status = 'error', error = %s, "
                                    "finished_at = now() WHERE id = %s", [str(e)[:200], job[0]])
                except Exception:
                    pass
            time.sleep(2)


@app.on_event("startup")
def _start_worker():
    threading.Thread(target=_worker_loop, name="sweep-worker", daemon=True).start()


# Static map UI at / (mounted last so /api/* and /sweep win).
app.mount("/", StaticFiles(directory="web", html=True), name="web")
