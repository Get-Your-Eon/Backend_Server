-- Safe script to populate station.location from charger.location
-- Behavior:
-- 1) For each station with NULL location, collect all non-null charger locations.
-- 2) Compute the centroid of those charger points and set station.location to that centroid
-- 3) Skip updates where centroid is (0,0)
-- 4) Update stations.updated_at to now()
-- Usage: run via psql (wrapper provided: scripts/fill_station_locations_from_chargers.sh)

BEGIN;

WITH charger_centroids AS (
  SELECT
    station_id,
    ST_SetSRID(ST_Centroid(ST_Collect(location)), 4326) AS centroid,
    COUNT(*) AS charger_count
  FROM chargers
  WHERE location IS NOT NULL
  GROUP BY station_id
), to_update AS (
  SELECT s.id AS station_id, c.centroid, c.charger_count
  FROM stations s
  JOIN charger_centroids c ON c.station_id = s.id
  -- only update stations that don't already have a location
  WHERE s.location IS NULL
    -- avoid bogus (0,0) points
    AND NOT (ST_X(c.centroid) = 0 AND ST_Y(c.centroid) = 0)
)
UPDATE stations s
SET location = t.centroid,
    updated_at = now()
FROM to_update t
WHERE s.id = t.station_id
RETURNING s.id AS station_id, t.charger_count;

COMMIT;

-- Notes:
-- - This script only updates stations with NULL location.
-- - It uses PostGIS functions; ensure PostGIS is enabled in the DB (it is in this project).
-- - The RETURNING output shows station IDs updated and how many chargers contributed.
