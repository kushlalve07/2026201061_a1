-- RideSync (Project 2) — Step 2: partial unique index
-- A rider may have at most one active trip at a time.
--
--   psql -U ridesync -d ridesync -f sql/02_indexes.sql

CREATE UNIQUE INDEX idx_active_rider_trip
    ON trips (rider_id)
    WHERE status IN ('REQUESTED', 'IN_TRANSIT');
