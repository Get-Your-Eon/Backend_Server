-- Divide sale_price by 10000 for subsidies where sale_price has at least four trailing zeros
-- Only affect rows where sale_price IS NOT NULL AND sale_price <> 0 AND sale_price % 10000 = 0
-- Usage: psql "<DB_URL>" -f scripts/update_saleprice_divide_10000.sql

BEGIN;

-- Preview counts
SELECT count(*) AS total_rows FROM subsidies;
SELECT count(*) AS affected_before FROM subsidies WHERE sale_price IS NOT NULL AND sale_price <> 0 AND sale_price % 10000 = 0;
SELECT count(*) AS zero_before FROM subsidies WHERE sale_price = 0;

-- Backup note: create a CSV backup before running this script (recommended).

-- Apply the update: divide by 10000 only when sale_price ends with 4 zeros and is not zero
UPDATE subsidies
SET sale_price = sale_price / 10000
WHERE sale_price IS NOT NULL AND sale_price <> 0 AND sale_price % 10000 = 0;

-- Verification
SELECT count(*) AS affected_after FROM subsidies WHERE sale_price IS NOT NULL AND sale_price <> 0 AND sale_price % 10000 = 0;
SELECT count(*) AS zero_after FROM subsidies WHERE sale_price = 0;

-- Show a few sample rows where change likely happened (order by id)
SELECT id, model_name, sale_price FROM subsidies WHERE sale_price IS NOT NULL ORDER BY id LIMIT 20;

COMMIT;

-- If anything looks wrong, restore from CSV backup created before running this script.
