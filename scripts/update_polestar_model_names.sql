-- Update Polestar model_name strings for 폴스타오토모티브코리아 / Polestar 4
-- Usage:
-- 1) Backup affected rows locally:
--    psql "$DATABASE_URL" -c "\COPY (SELECT * FROM subsidies WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4') TO 'polestar_affected_rows.csv' CSV HEADER;"
-- 2) Run this file against the target DB (in a safe time window):
--    psql "$DATABASE_URL" -f scripts/update_polestar_model_names.sql

BEGIN;

-- Safety checks: counts before
SELECT count(*) AS total_polestar_rows FROM subsidies WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4';
SELECT count(*) AS single_motor_before FROM subsidies WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4' AND model_name = E'Polestar 4 Long Range Single Motor';
SELECT count(*) AS dual_22_before FROM subsidies WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4' AND model_name = E'Polestar 4 Long Range Dual Motor 22인치';
SELECT count(*) AS dual_20star21_before FROM subsidies WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4' AND model_name = E'Polestar 4 Long Range Dual Motor 20*21인치';

-- 1) Single Motor -> add wheel size suffix "20인치"
UPDATE subsidies
SET model_name = E'Polestar 4 Long Range Single Motor 20인치'
WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4' AND model_name = E'Polestar 4 Long Range Single Motor';

-- 2) Dual Motor 22인치 -> add " performance" suffix
UPDATE subsidies
SET model_name = E'Polestar 4 Long Range Dual Motor 22인치 performance'
WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4' AND model_name = E'Polestar 4 Long Range Dual Motor 22인치';

-- 3) Dual Motor 20*21인치 -> normalize to "20인치"
UPDATE subsidies
SET model_name = E'Polestar 4 Long Range Dual Motor 20인치'
WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4' AND model_name = E'Polestar 4 Long Range Dual Motor 20*21인치';

-- Verification: counts after
SELECT count(*) AS single_motor_after FROM subsidies WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4' AND model_name = E'Polestar 4 Long Range Single Motor 20인치';
SELECT count(*) AS dual_22_after FROM subsidies WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4' AND model_name = E'Polestar 4 Long Range Dual Motor 22인치 performance';
SELECT count(*) AS dual_20_after FROM subsidies WHERE manufacturer = E'폴스타오토모티브코리아' AND model_group = E'Polestar 4' AND model_name = E'Polestar 4 Long Range Dual Motor 20인치';

COMMIT;

-- If anything looks wrong, you can restore from the CSV backup with a small script or manually.
