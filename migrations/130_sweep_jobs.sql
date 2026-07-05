-- Queue of area sweeps. A background worker drains pending jobs FIFO, so several
-- areas can be stacked and scored unattended (no browser held open). Each row is
-- also a record of WHERE we swept, which the map draws as a coverage layer.

CREATE TABLE IF NOT EXISTS sweep_jobs (
    id           BIGSERIAL PRIMARY KEY,
    lat          DOUBLE PRECISION NOT NULL,
    lon          DOUBLE PRECISION NOT NULL,
    radius_mi    DOUBLE PRECISION NOT NULL,
    mode         TEXT NOT NULL DEFAULT 'moto',   -- moto | couple
    status       TEXT NOT NULL DEFAULT 'pending', -- pending | running | done | error
    towns_total  INTEGER,
    towns_done   INTEGER NOT NULL DEFAULT 0,
    error        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS sweep_jobs_status_idx ON sweep_jobs (status);
CREATE INDEX IF NOT EXISTS sweep_jobs_created_idx ON sweep_jobs (created_at);
