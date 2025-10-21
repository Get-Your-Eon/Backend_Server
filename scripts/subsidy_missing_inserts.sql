-- Inserts for subsidy rows found in CSV but missing from DB
BEGIN;
-- Volvo EX30 missing row
DELETE FROM subsidies WHERE manufacturer = E'볼보자동차코리아' AND model_group = E'EX30' AND model_name = E'볼보 EX 30cc Twin';
INSERT INTO subsidies (manufacturer, model_group, model_name, subsidy_national_10k_won, subsidy_local_10k_won, subsidy_total_10k_won) VALUES (E'볼보자동차코리아', E'EX30', E'볼보 EX 30cc Twin', 111, 57, 168);

-- ensure sequence is set to max id
SELECT setval('subsidies_id_seq', COALESCE((SELECT MAX(id) FROM subsidies), 1), true);
COMMIT;
