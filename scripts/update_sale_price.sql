-- Safe update script for subsidies.sale_price
-- Generated: 2025-10-29
-- Usage: review the preview SELECT, then run in psql or via your migration tooling.

BEGIN;

-- Preview rows that will be affected (exact model_name match)
SELECT id, model_name, sale_price
FROM subsidies
WHERE model_name IN (
  'GV60 스탠다드 2WD 19인치',
  'GV60 스탠다드 AWD 19인치',
  'GV60 스탠다드 AWD 20인치',
  'GV60 퍼포먼스 AWD 21인치',
  'Electrified GV70 AWD 20인치',
  'Electrified GV70 AWD 19인치',
  '아이오닉6 스탠다드 2WD 18인치',
  '아이오닉6 롱레인지 2WD 18인치',
  '아이오닉6 롱레인지 2WD 20인치',
  '아이오닉6 롱레인지 AWD 18인치',
  '아이오닉6 롱레인지 AWD 20인치',
  '코나 일렉트릭 2WD 스탠다드 17인치',
  '코나 일렉트릭 2WD 롱레인지 17인치',
  '코나 일렉트릭 2WD 롱레인지 19인치(빌트인 캠)',
  '아이오닉5 N',
  '더뉴아이오닉5 2WD 롱레인지 19인치 빌트인 캠 미적용',
  '더뉴아이오닉5 2WD 롱레인지 19인치',
  '더뉴아이오닉5 2WD 롱레인지 20인치',
  '더뉴아이오닉5 AWD 롱레인지 20인치',
  '더뉴아이오닉5 AWD 롱레인지 19인치',
  '더뉴아이오닉5 2WD 롱레인지 N라인 20인치',
  '더뉴아이오닉5 AWD 롱레인지 N라인 20인치',
  'Electrified G80 AWD 19인치(2025)',
  '더뉴아이오닉5 2WD 스탠다드 19인치',
  'Electrified GV70 AWD 20인치(2025)',
  'Electrified GV70 AWD 19인치(2025)',
  '코나 일렉트릭 2WD 롱레인지 17인치(빌트인 캠)',
  '아이오닉9 성능형 AWD',
  '아이오닉9 항속형 AWD',
  '아이오닉9 항속형 2WD',
  'GV60 퍼포먼스 AWD 21인치(2025)',
  'GV60 스탠다드 AWD 20인치(2025)',
  'GV60 스탠다드 AWD 19인치(2025)',
  'GV60 스탠다드 2WD 19인치(2025)',
  '더 뉴 아이오닉6 2wd 롱레인지 n라인 20인치',
  '더 뉴 아이오닉6 awd 롱레인지 n라인 20인치',
  '더 뉴 아이오닉6 2wd 롱레인지 18인치',
  '더 뉴 아이오닉6 2wd 롱레인지 20인치',
  '더 뉴 아이오닉6 awd 롱레인지 18인치',
  '더 뉴 아이오닉6 awd 롱레인지 20인치',
  '더 뉴 아이오닉6 2wd 스탠다드 18인치',
  'The all-new Kia Niro EV',
  'EV9 롱레인지 2WD 19인치',
  'EV9 롱레인지 2WD 20인치',
  'EV9 롱레인지 4WD 19인치',
  'EV9 롱레인지 4WD 21인치',
  'EV9 롱레인지 GTL 4WD 21인치',
  '더뉴EV6 롱레인지 4WD 20인치',
  '더뉴EV6 롱레인지 2WD 20인치',
  '더뉴EV6 롱레인지 4WD 19인치',
  '더뉴EV6 롱레인지 2WD 19인치',
  'EV3 롱레인지 2WD 17인치',
  'EV3 롱레인지 2WD 19인치',
  'EV3 스탠다드 2WD',
  '더뉴EV6 GT',
  '더뉴EV6 스탠다드',
  'EV9 스탠다드',
  'EV4 롱레인지 GTL 2WD 19인치',
  'EV4 스탠다드 2WD 19인치',
  'EV4 롱레인지 2WD 17인치',
  'EV4 롱레인지 2WD 19인치',
  'EV4 스탠다드 2WD 17인치',
  'PV5 패신저 5인승 롱레인지',
  'EV5 롱레인지 2WD',
  'scenic',
  'MINI Cooper SE',
  'i4 eDrive40',
  'i4 M50',
  'iX1 xDrive30',
  'i4 eDrive40 LCI',
  'iX2 eDrive20',
  'MINI Countryman SE ALL4',
  'MINI Countryman E',
  'MINI Aceman SE',
  'i4 M50 LCI',
  'MINI JCW Aceman E',
  'MINI JCW E',
  'MINI Aceman E',
  'ix1 edrive20',
  'i5 edrive 40',
  '(단종)Model 3 RWD(2024)',
  '(단종)Model Y RWD',
  'Model 3 Long Range',
  '(단종)Model Y Long Range',
  '(단종)Model Y Performance',
  'Model 3 Performance',
  '(단종)Model Y Long Range 19인치',
  'Model 3 RWD',
  'New Model Y Long Range',
  'New Model Y RWD',
  '(단종)EQB300 4MATIC(Pre-Facelift)(5인승)',
  '(단종)EQB300 4MATIC(Pre-Facelift)(7인승)',
  'EQA250(Facelift)',
  'EQB300 4MATIC(Facelift)(5인승)',
  'EQB300 4MATIC(Facelift)(7인승)',
  '(단종)아우디 Q4 40 e-tron',
  '(단종)아우디 Q4 Sportback 40 e-tron',
  '아우디 Q4 Sportback 45 e-tron',
  '아우디 Q4 45 e-tron',
  '코란도 EV 2WD',
  '토레스 EVX 2WD 18인치',
  '토레스 EVX 2WD 20인치',
  '토레스 EVX 18인치',
  '토레스 EVX 20인치',
  'Polestar 4 Long Range Single Motor',
  'Polestar 4 Long Range Dual Motor 22인치',
  'Polestar 4 Long Range Dual Motor 20*21인치',
  '볼보 EX30 Single Motor ER',
  '볼보 EX 30cc Twin',
  'BYD ATTO 3',
  'BYD SEAL Dynamic awd'
);

-- Per-row updates: only update when sale_price IS NULL or different from the given value
UPDATE subsidies SET sale_price = 68360000 WHERE model_name = 'GV60 스탠다드 2WD 19인치' AND (sale_price IS NULL OR sale_price <> 68360000);
UPDATE subsidies SET sale_price = 72160000 WHERE model_name = 'GV60 스탠다드 AWD 19인치' AND (sale_price IS NULL OR sale_price <> 72160000);
UPDATE subsidies SET sale_price = 74460000 WHERE model_name = 'GV60 스탠다드 AWD 20인치' AND (sale_price IS NULL OR sale_price <> 74460000);
UPDATE subsidies SET sale_price = 76760000 WHERE model_name = 'GV60 퍼포먼스 AWD 21인치' AND (sale_price IS NULL OR sale_price <> 76760000);
UPDATE subsidies SET sale_price = 80110000 WHERE model_name = 'Electrified GV70 AWD 20인치' AND (sale_price IS NULL OR sale_price <> 80110000);
UPDATE subsidies SET sale_price = 79310000 WHERE model_name = 'Electrified GV70 AWD 19인치' AND (sale_price IS NULL OR sale_price <> 79310000);
UPDATE subsidies SET sale_price = 49450000 WHERE model_name = '아이오닉6 스탠다드 2WD 18인치' AND (sale_price IS NULL OR sale_price <> 49450000);
UPDATE subsidies SET sale_price = 53300000 WHERE model_name = '아이오닉6 롱레인지 2WD 18인치' AND (sale_price IS NULL OR sale_price <> 53300000);
UPDATE subsidies SET sale_price = 59310000 WHERE model_name = '아이오닉6 롱레인지 2WD 20인치' AND (sale_price IS NULL OR sale_price <> 59310000);
UPDATE subsidies SET sale_price = 59400000 WHERE model_name = '아이오닉6 롱레인지 AWD 18인치' AND (sale_price IS NULL OR sale_price <> 59400000);
UPDATE subsidies SET sale_price = 61780000 WHERE model_name = '아이오닉6 롱레인지 AWD 20인치' AND (sale_price IS NULL OR sale_price <> 61780000);
UPDATE subsidies SET sale_price = 43070000 WHERE model_name = '코나 일렉트릭 2WD 스탠다드 17인치' AND (sale_price IS NULL OR sale_price <> 43070000);
UPDATE subsidies SET sale_price = 48310000 WHERE model_name = '코나 일렉트릭 2WD 롱레인지 17인치' AND (sale_price IS NULL OR sale_price <> 48310000);
UPDATE subsidies SET sale_price = 49050000 WHERE model_name = '코나 일렉트릭 2WD 롱레인지 19인치(빌트인 캠)' AND (sale_price IS NULL OR sale_price <> 49050000);
UPDATE subsidies SET sale_price = 78800000 WHERE model_name = '아이오닉5 N' AND (sale_price IS NULL OR sale_price <> 78800000);
UPDATE subsidies SET sale_price = 56550000 WHERE model_name = '더뉴아이오닉5 2WD 롱레인지 19인치 빌트인 캠 미적용' AND (sale_price IS NULL OR sale_price <> 56550000);
UPDATE subsidies SET sale_price = 58630000 WHERE model_name = '더뉴아이오닉5 2WD 롱레인지 19인치' AND (sale_price IS NULL OR sale_price <> 58630000);
UPDATE subsidies SET sale_price = 59510000 WHERE model_name = '더뉴아이오닉5 2WD 롱레인지 20인치' AND (sale_price IS NULL OR sale_price <> 59510000);
UPDATE subsidies SET sale_price = 63810000 WHERE model_name = '더뉴아이오닉5 AWD 롱레인지 20인치' AND (sale_price IS NULL OR sale_price <> 63810000);
UPDATE subsidies SET sale_price = 62520000 WHERE model_name = '더뉴아이오닉5 AWD 롱레인지 19인치' AND (sale_price IS NULL OR sale_price <> 62520000);
UPDATE subsidies SET sale_price = 62520000 WHERE model_name = '더뉴아이오닉5 2WD 롱레인지 N라인 20인치' AND (sale_price IS NULL OR sale_price <> 62520000);
UPDATE subsidies SET sale_price = 64950000 WHERE model_name = '더뉴아이오닉5 AWD 롱레인지 N라인 20인치' AND (sale_price IS NULL OR sale_price <> 64950000);
UPDATE subsidies SET sale_price = 84680000 WHERE model_name = 'Electrified G80 AWD 19인치(2025)' AND (sale_price IS NULL OR sale_price <> 84680000);
UPDATE subsidies SET sale_price = 52980000 WHERE model_name = '더뉴아이오닉5 2WD 스탠다드 19인치' AND (sale_price IS NULL OR sale_price <> 52980000);
UPDATE subsidies SET sale_price = 80110000 WHERE model_name = 'Electrified GV70 AWD 20인치(2025)' AND (sale_price IS NULL OR sale_price <> 80110000);
UPDATE subsidies SET sale_price = 79310000 WHERE model_name = 'Electrified GV70 AWD 19인치(2025)' AND (sale_price IS NULL OR sale_price <> 79310000);
UPDATE subsidies SET sale_price = 50860000 WHERE model_name = '코나 일렉트릭 2WD 롱레인지 17인치(빌트인 캠)' AND (sale_price IS NULL OR sale_price <> 50860000);
UPDATE subsidies SET sale_price = 72550000 WHERE model_name = '아이오닉9 성능형 AWD' AND (sale_price IS NULL OR sale_price <> 72550000);
UPDATE subsidies SET sale_price = 71690000 WHERE model_name = '아이오닉9 항속형 AWD' AND (sale_price IS NULL OR sale_price <> 71690000);
UPDATE subsidies SET sale_price = 69030000 WHERE model_name = '아이오닉9 항속형 2WD' AND (sale_price IS NULL OR sale_price <> 69030000);
UPDATE subsidies SET sale_price = 76760000 WHERE model_name = 'GV60 퍼포먼스 AWD 21인치(2025)' AND (sale_price IS NULL OR sale_price <> 76760000);
UPDATE subsidies SET sale_price = 74460000 WHERE model_name = 'GV60 스탠다드 AWD 20인치(2025)' AND (sale_price IS NULL OR sale_price <> 74460000);
UPDATE subsidies SET sale_price = 72160000 WHERE model_name = 'GV60 스탠다드 AWD 19인치(2025)' AND (sale_price IS NULL OR sale_price <> 72160000);
UPDATE subsidies SET sale_price = 68360000 WHERE model_name = 'GV60 스탠다드 2WD 19인치(2025)' AND (sale_price IS NULL OR sale_price <> 68360000);
UPDATE subsidies SET sale_price = 58720000 WHERE model_name = '더 뉴 아이오닉6 2wd 롱레인지 n라인 20인치' AND (sale_price IS NULL OR sale_price <> 58720000);
UPDATE subsidies SET sale_price = 61780000 WHERE model_name = '더 뉴 아이오닉6 awd 롱레인지 n라인 20인치' AND (sale_price IS NULL OR sale_price <> 61780000);
UPDATE subsidies SET sale_price = 53300000 WHERE model_name = '더 뉴 아이오닉6 2wd 롱레인지 18인치' AND (sale_price IS NULL OR sale_price <> 53300000);
UPDATE subsidies SET sale_price = 59310000 WHERE model_name = '더 뉴 아이오닉6 2wd 롱레인지 20인치' AND (sale_price IS NULL OR sale_price <> 59310000);
UPDATE subsidies SET sale_price = 59400000 WHERE model_name = '더 뉴 아이오닉6 awd 롱레인지 18인치' AND (sale_price IS NULL OR sale_price <> 59400000);
UPDATE subsidies SET sale_price = 61780000 WHERE model_name = '더 뉴 아이오닉6 awd 롱레인지 20인치' AND (sale_price IS NULL OR sale_price <> 61780000);
UPDATE subsidies SET sale_price = 49450000 WHERE model_name = '더 뉴 아이오닉6 2wd 스탠다드 18인치' AND (sale_price IS NULL OR sale_price <> 49450000);
UPDATE subsidies SET sale_price = 32060000 WHERE model_name = 'The all-new Kia Niro EV' AND (sale_price IS NULL OR sale_price <> 32060000);
UPDATE subsidies SET sale_price = 64120000 WHERE model_name = 'EV9 롱레인지 2WD 19인치' AND (sale_price IS NULL OR sale_price <> 64120000);
UPDATE subsidies SET sale_price = 64590000 WHERE model_name = 'EV9 롱레인지 2WD 20인치' AND (sale_price IS NULL OR sale_price <> 64590000);
UPDATE subsidies SET sale_price = 68570000 WHERE model_name = 'EV9 롱레인지 4WD 19인치' AND (sale_price IS NULL OR sale_price <> 68570000);
UPDATE subsidies SET sale_price = 69040000 WHERE model_name = 'EV9 롱레인지 4WD 21인치' AND (sale_price IS NULL OR sale_price <> 69040000);
UPDATE subsidies SET sale_price = 73360000 WHERE model_name = 'EV9 롱레인지 GTL 4WD 21인치' AND (sale_price IS NULL OR sale_price <> 73360000);
UPDATE subsidies SET sale_price = 49080000 WHERE model_name = '더뉴EV6 롱레인지 4WD 20인치' AND (sale_price IS NULL OR sale_price <> 49080000);
UPDATE subsidies SET sale_price = 46600000 WHERE model_name = '더뉴EV6 롱레인지 2WD 20인치' AND (sale_price IS NULL OR sale_price <> 46600000);
UPDATE subsidies SET sale_price = 46600000 WHERE model_name = '더뉴EV6 롱레인지 4WD 19인치' AND (sale_price IS NULL OR sale_price <> 46600000);
UPDATE subsidies SET sale_price = 46600000 WHERE model_name = '더뉴EV6 롱레인지 2WD 19인치' AND (sale_price IS NULL OR sale_price <> 46600000);
UPDATE subsidies SET sale_price = 39950000 WHERE model_name = 'EV3 롱레인지 2WD 17인치' AND (sale_price IS NULL OR sale_price <> 39950000);
UPDATE subsidies SET sale_price = 39950000 WHERE model_name = 'EV3 롱레인지 2WD 19인치' AND (sale_price IS NULL OR sale_price <> 39950000);
UPDATE subsidies SET sale_price = 39950000 WHERE model_name = 'EV3 스탠다드 2WD' AND (sale_price IS NULL OR sale_price <> 39950000);
UPDATE subsidies SET sale_price = 39950000 WHERE model_name = '더뉴EV6 GT' AND (sale_price IS NULL OR sale_price <> 39950000);
UPDATE subsidies SET sale_price = 39950000 WHERE model_name = '더뉴EV6 스탠다드' AND (sale_price IS NULL OR sale_price <> 39950000);
UPDATE subsidies SET sale_price = 64120000 WHERE model_name = 'EV9 스탠다드' AND (sale_price IS NULL OR sale_price <> 64120000);
UPDATE subsidies SET sale_price = 40420000 WHERE model_name = 'EV4 롱레인지 GTL 2WD 19인치' AND (sale_price IS NULL OR sale_price <> 40420000);
UPDATE subsidies SET sale_price = 40420000 WHERE model_name = 'EV4 스탠다드 2WD 19인치' AND (sale_price IS NULL OR sale_price <> 40420000);
UPDATE subsidies SET sale_price = 40420000 WHERE model_name = 'EV4 롱레인지 2WD 17인치' AND (sale_price IS NULL OR sale_price <> 40420000);
UPDATE subsidies SET sale_price = 40420000 WHERE model_name = 'EV4 롱레인지 2WD 19인치' AND (sale_price IS NULL OR sale_price <> 40420000);
UPDATE subsidies SET sale_price = 40420000 WHERE model_name = 'EV4 스탠다드 2WD 17인치' AND (sale_price IS NULL OR sale_price <> 40420000);
UPDATE subsidies SET sale_price = 45400000 WHERE model_name = 'PV5 패신저 5인승 롱레인지' AND (sale_price IS NULL OR sale_price <> 45400000);
UPDATE subsidies SET sale_price = 48550000 WHERE model_name = 'EV5 롱레인지 2WD' AND (sale_price IS NULL OR sale_price <> 48550000);
UPDATE subsidies SET sale_price = 46780000 WHERE model_name = 'scenic' AND (sale_price IS NULL OR sale_price <> 46780000);
UPDATE subsidies SET sale_price = 52500000 WHERE model_name = 'MINI Cooper SE' AND (sale_price IS NULL OR sale_price <> 52500000);
UPDATE subsidies SET sale_price = 78300000 WHERE model_name = 'i4 eDrive40' AND (sale_price IS NULL OR sale_price <> 78300000);
UPDATE subsidies SET sale_price = 84900000 WHERE model_name = 'i4 M50' AND (sale_price IS NULL OR sale_price <> 84900000);
UPDATE subsidies SET sale_price = 67900000 WHERE model_name = 'iX1 xDrive30' AND (sale_price IS NULL OR sale_price <> 67900000);
UPDATE subsidies SET sale_price = 78300000 WHERE model_name = 'i4 eDrive40 LCI' AND (sale_price IS NULL OR sale_price <> 78300000);
UPDATE subsidies SET sale_price = 65700000 WHERE model_name = 'iX2 eDrive20' AND (sale_price IS NULL OR sale_price <> 65700000);
UPDATE subsidies SET sale_price = 0 WHERE model_name = 'MINI Countryman SE ALL4' AND (sale_price IS NULL OR sale_price <> 0);
UPDATE subsidies SET sale_price = 56700000 WHERE model_name = 'MINI Countryman E' AND (sale_price IS NULL OR sale_price <> 56700000);
UPDATE subsidies SET sale_price = 58000000 WHERE model_name = 'MINI Aceman SE' AND (sale_price IS NULL OR sale_price <> 58000000);
UPDATE subsidies SET sale_price = 84900000 WHERE model_name = 'i4 M50 LCI' AND (sale_price IS NULL OR sale_price <> 84900000);
UPDATE subsidies SET sale_price = 0 WHERE model_name = 'MINI JCW Aceman E' AND (sale_price IS NULL OR sale_price <> 0);
UPDATE subsidies SET sale_price = 0 WHERE model_name = 'MINI JCW E' AND (sale_price IS NULL OR sale_price <> 0);
UPDATE subsidies SET sale_price = 49700000 WHERE model_name = 'MINI Aceman E' AND (sale_price IS NULL OR sale_price <> 49700000);
UPDATE subsidies SET sale_price = 65700000 WHERE model_name = 'ix1 edrive20' AND (sale_price IS NULL OR sale_price <> 65700000);
UPDATE subsidies SET sale_price = 84900000 WHERE model_name = 'i5 edrive 40' AND (sale_price IS NULL OR sale_price <> 84900000);
UPDATE subsidies SET sale_price = 51990000 WHERE model_name = '(단종)Model 3 RWD(2024)' AND (sale_price IS NULL OR sale_price <> 51990000);
UPDATE subsidies SET sale_price = 52990000 WHERE model_name = '(단종)Model Y RWD' AND (sale_price IS NULL OR sale_price <> 52990000);
UPDATE subsidies SET sale_price = 59990000 WHERE model_name = 'Model 3 Long Range' AND (sale_price IS NULL OR sale_price <> 59990000);
UPDATE subsidies SET sale_price = 63140000 WHERE model_name = '(단종)Model Y Long Range' AND (sale_price IS NULL OR sale_price <> 63140000);
UPDATE subsidies SET sale_price = 8043000 WHERE model_name = '(단종)Model Y Performance' AND (sale_price IS NULL OR sale_price <> 8043000);
UPDATE subsidies SET sale_price = 69390000 WHERE model_name = 'Model 3 Performance' AND (sale_price IS NULL OR sale_price <> 69390000);
UPDATE subsidies SET sale_price = 63140000 WHERE model_name = '(단종)Model Y Long Range 19인치' AND (sale_price IS NULL OR sale_price <> 63140000);
UPDATE subsidies SET sale_price = 51990000 WHERE model_name = 'Model 3 RWD' AND (sale_price IS NULL OR sale_price <> 51990000);
UPDATE subsidies SET sale_price = 63140000 WHERE model_name = 'New Model Y Long Range' AND (sale_price IS NULL OR sale_price <> 63140000);
UPDATE subsidies SET sale_price = 52990000 WHERE model_name = 'New Model Y RWD' AND (sale_price IS NULL OR sale_price <> 52990000);
UPDATE subsidies SET sale_price = 78100000 WHERE model_name = '(단종)EQB300 4MATIC(Pre-Facelift)(5인승)' AND (sale_price IS NULL OR sale_price <> 78100000);
UPDATE subsidies SET sale_price = 78100000 WHERE model_name = '(단종)EQB300 4MATIC(Pre-Facelift)(7인승)' AND (sale_price IS NULL OR sale_price <> 78100000);
UPDATE subsidies SET sale_price = 70000000 WHERE model_name = 'EQA250(Facelift)' AND (sale_price IS NULL OR sale_price <> 70000000);
UPDATE subsidies SET sale_price = 78100000 WHERE model_name = 'EQB300 4MATIC(Facelift)(5인승)' AND (sale_price IS NULL OR sale_price <> 78100000);
UPDATE subsidies SET sale_price = 78100000 WHERE model_name = 'EQB300 4MATIC(Facelift)(7인승)' AND (sale_price IS NULL OR sale_price <> 78100000);
UPDATE subsidies SET sale_price = 68893000 WHERE model_name = '(단종)아우디 Q4 40 e-tron' AND (sale_price IS NULL OR sale_price <> 68893000);
UPDATE subsidies SET sale_price = 72700000 WHERE model_name = '(단종)아우디 Q4 Sportback 40 e-tron' AND (sale_price IS NULL OR sale_price <> 72700000);
UPDATE subsidies SET sale_price = 0 WHERE model_name = '아우디 Q4 Sportback 45 e-tron' AND (sale_price IS NULL OR sale_price <> 0);
UPDATE subsidies SET sale_price = 0 WHERE model_name = '아우디 Q4 45 e-tron' AND (sale_price IS NULL OR sale_price <> 0);
UPDATE subsidies SET sale_price = 31500000 WHERE model_name = '코란도 EV 2WD' AND (sale_price IS NULL OR sale_price <> 31500000);
UPDATE subsidies SET sale_price = 48470000 WHERE model_name = '토레스 EVX 2WD 18인치' AND (sale_price IS NULL OR sale_price <> 48470000);
UPDATE subsidies SET sale_price = 50680000 WHERE model_name = '토레스 EVX 2WD 20인치' AND (sale_price IS NULL OR sale_price <> 50680000);
UPDATE subsidies SET sale_price = 44380000 WHERE model_name = '토레스 EVX 18인치' AND (sale_price IS NULL OR sale_price <> 44380000);
UPDATE subsidies SET sale_price = 46290000 WHERE model_name = '토레스 EVX 20인치' AND (sale_price IS NULL OR sale_price <> 46290000);
UPDATE subsidies SET sale_price = 66900000 WHERE model_name = 'Polestar 4 Long Range Single Motor' AND (sale_price IS NULL OR sale_price <> 66900000);
UPDATE subsidies SET sale_price = 83900000 WHERE model_name = 'Polestar 4 Long Range Dual Motor 22인치' AND (sale_price IS NULL OR sale_price <> 83900000);
UPDATE subsidies SET sale_price = 71900000 WHERE model_name = 'Polestar 4 Long Range Dual Motor 20*21인치' AND (sale_price IS NULL OR sale_price <> 71900000);
UPDATE subsidies SET sale_price = 47520000 WHERE model_name = '볼보 EX30 Single Motor ER' AND (sale_price IS NULL OR sale_price <> 47520000);
UPDATE subsidies SET sale_price = 51790000 WHERE model_name = '볼보 EX 30cc Twin' AND (sale_price IS NULL OR sale_price <> 51790000);
UPDATE subsidies SET sale_price = 31500000 WHERE model_name = 'BYD ATTO 3' AND (sale_price IS NULL OR sale_price <> 31500000);
UPDATE subsidies SET sale_price = 46900000 WHERE model_name = 'BYD SEAL Dynamic awd' AND (sale_price IS NULL OR sale_price <> 46900000);

-- After running: run the preview SELECT above again to confirm changes, or check counts below
SELECT COUNT(*) AS total_subsidies, COUNT(sale_price) AS sale_price_set FROM subsidies;

COMMIT;

-- If you want to abort instead of commit, run: ROLLBACK;
