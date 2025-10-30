-- Update BYD SEAL model_name formatting for 비와이디코리아 / SEAL
-- Usage: psql "<DB_URL>" -f scripts/update_byd_seal.sql

BEGIN;

-- Pre-check counts
SELECT count(*) AS before_old_name FROM subsidies WHERE manufacturer = E'비와이디코리아' AND model_group = E'SEAL' AND model_name = E'byd seal dynamic awd';
SELECT count(*) AS before_new_name FROM subsidies WHERE manufacturer = E'비와이디코리아' AND model_group = E'SEAL' AND model_name = E'BYD SEAL Dynamic awd';

-- Apply update
UPDATE subsidies
SET model_name = E'BYD SEAL Dynamic awd'
WHERE manufacturer = E'비와이디코리아' AND model_group = E'SEAL' AND model_name = E'byd seal dynamic awd';

-- Post-check
SELECT count(*) AS after_old_name FROM subsidies WHERE manufacturer = E'비와이디코리아' AND model_group = E'SEAL' AND model_name = E'byd seal dynamic awd';
SELECT count(*) AS after_new_name FROM subsidies WHERE manufacturer = E'비와이디코리아' AND model_group = E'SEAL' AND model_name = E'BYD SEAL Dynamic awd';
SELECT id, manufacturer, model_group, model_name, subsidy_total_10k_won FROM subsidies WHERE manufacturer = E'비와이디코리아' AND model_group = E'SEAL' ORDER BY id;

COMMIT;

-- If results are unexpected, restore from backup CSV files created before running this script.
