-- Cache of Google Place Details responses (the parsed dict places.place_details
-- returns). The same motel/diner is re-fetched for every trip mode, re-score and
-- overlapping sweep; at the Enterprise+Atmosphere SKU that is the second-biggest
-- Places cost. Rows older than PLACE_DETAILS_TTL_DAYS are refetched.
-- Note: Google's Maps Platform terms only allow place_id to be stored long-term;
-- other content is meant for short-term caching. Personal, single-user app —
-- shorten PLACE_DETAILS_TTL_DAYS if that ever matters.

CREATE TABLE IF NOT EXISTS place_details (
    place_id    TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
