-- Cache of Google Place Details responses (the parsed dict places.place_details
-- returns). The same motel/diner is re-fetched for every trip mode, re-score and
-- overlapping sweep; at the Enterprise+Atmosphere SKU that is the second-biggest
-- Places cost. Rows older than PLACE_DETAILS_TTL_DAYS are refetched.

CREATE TABLE IF NOT EXISTS place_details (
    place_id    TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
