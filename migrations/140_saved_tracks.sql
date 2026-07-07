-- The current imported track (route overlay), persisted server-side so it shows
-- on any browser or device. This app has no auth and its data is all shared, so
-- this is one shared "current track" — replaced on each import, matching the
-- single-track map UI.

CREATE TABLE IF NOT EXISTS saved_tracks (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT,
    geojson     JSONB NOT NULL,
    gpx         TEXT NOT NULL,
    counts      JSONB,
    skipped     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
