#!/usr/bin/env python3
"""
Generate SQL to insert subsidy rows from a CSV file.

Produces a file with a transactional block that deletes existing rows for
the same manufacturer/model_group/model_name and inserts normalized values.

Usage:
  python scripts/generate_subsidy_inserts.py --csv /path/to/subsidy.csv --out scripts/subsidies_inserts.sql --no-filter

By default the script filters rows according to a provided mapping of
manufacturers -> allowed model_groups. Use --no-filter to include all rows.
"""
import argparse
import csv
import sys
from pathlib import Path


car_categories = {
    "현대자동차": {"GV60", "GV70", "G80", "아이오닉5", "아이오닉6", "아이오닉9", "코나 EV"},
    "기아": {"Niro EV", "EV9", "EV6", "EV3", "EV4", "EV5", "PV5"},
    "르노코리아": {"scenic"},
    "BMW": {"i4", "i5", "iX1", "iX2", "MINI"},
    "테슬라코리아": {"Model 3", "Model Y"},
    "메르세데스벤츠코리아": {"EQB", "EQA"},
    "폭스바겐그룹코리아": {"아우디 Q4", "아우디 Q6", "폭스바겐 ID.4", "폭스바겐 ID.5"},
    "케이지모빌리티": {"토레스 EVX", "코란도 EV"},
    "폴스타오토모티브코리아": {"Polestar 4"},
    "볼보자동차코리아": {"EX30"},
    "비와이디코리아": {"ATTO 3", "SEAL"},
}


def parse_int(val):
    if val is None:
        return None
    v = str(val).strip()
    if v == "":
        return None
    # remove commas and non-digit characters except minus
    v = v.replace(',', '').replace(' ', '')
    try:
        return int(float(v))
    except Exception:
        return None


def esc(s: str) -> str:
    return s.replace("'", "''")


def generate(sql_out: Path, csv_path: Path, filter_by_categories: bool = True):
    rows = []
    with csv_path.open('r', encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        for i, r in enumerate(reader, start=1):
            manu = (r.get('제조사') or r.get('manufacturer') or '').strip()
            model_group = (r.get('모델그룹') or r.get('model_group') or '').strip()
            model_name = (r.get('모델명') or r.get('model_name') or '').strip()
            nat = parse_int(r.get('국비(만원)') or r.get('national') or r.get('국비') or r.get('국비(만원)'))
            loc = parse_int(r.get('지방비(만원)') or r.get('local') or r.get('지방비') or r.get('지방비(만원)'))
            tot = parse_int(r.get('보조금(만원)') or r.get('total') or r.get('보조금') or r.get('보조금(만원)'))
            if tot is None and nat is not None and loc is not None:
                tot = nat + loc

            if not manu:
                print(f"skipping row {i}: empty manufacturer", file=sys.stderr)
                continue

            # If CSV does not include a model_group, try to infer it from model_name
            if model_group == '':
                inferred = None
                allowed = car_categories.get(manu)
                if allowed:
                    # prefer the longest matching substring to avoid partial hits
                    lower_name = model_name.lower()
                    candidates = [mg for mg in allowed if mg.lower() in lower_name]
                    if candidates:
                        inferred = max(candidates, key=lambda s: len(s))
                if inferred:
                    model_group = inferred
                else:
                    # leave model_group blank for now; filtering below will decide
                    model_group = ''

            if filter_by_categories:
                allowed = car_categories.get(manu)
                if allowed is None:
                    print(f"skipping row {i}: manufacturer '{manu}' not in car_categories", file=sys.stderr)
                    continue
                if model_group == '' or model_group not in allowed:
                    print(f"skipping row {i}: model_group '{model_group}' not allowed for manufacturer '{manu}'", file=sys.stderr)
                    continue

            rows.append({
                'manufacturer': manu,
                'model_group': model_group,
                'model_name': model_name,
                'national': nat if nat is not None else 'NULL',
                'local': loc if loc is not None else 'NULL',
                'total': tot if tot is not None else 'NULL',
            })

    # write SQL
    with sql_out.open('w', encoding='utf-8') as out:
        out.write('-- Generated subsidy inserts\n')
        out.write('BEGIN;\n')
        for r in rows:
            manu = esc(r['manufacturer'])
            mg = esc(r['model_group'])
            mn = esc(r['model_name'])
            nat = r['national']
            loc = r['local']
            tot = r['total']

            out.write(f"-- {manu} | {mg} | {mn}\n")
            out.write("DELETE FROM subsidies WHERE manufacturer = E'" + manu + "' AND model_group = E'" + mg + "' AND model_name = E'" + mn + "';\n")
            out.write("INSERT INTO subsidies (manufacturer, model_group, model_name, subsidy_national_10k_won, subsidy_local_10k_won, subsidy_total_10k_won) VALUES ("
                      + "E'" + manu + "', E'" + mg + "', E'" + mn + "', "
                      + (str(nat) if isinstance(nat, int) else 'NULL') + ", "
                      + (str(loc) if isinstance(loc, int) else 'NULL') + ", "
                      + (str(tot) if isinstance(tot, int) else 'NULL') + ");\n\n")

        out.write("-- ensure sequence is set to max id\n")
        out.write("SELECT setval('subsidies_id_seq', COALESCE((SELECT MAX(id) FROM subsidies), 1), true);\n")
        out.write('COMMIT;\n')

    print(f"Wrote {len(rows)} subsidy statements to {sql_out}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--csv', '-c', type=Path, default=Path('subsidy.csv'), help='Path to CSV file (utf-8 or utf-8-sig)')
    p.add_argument('--out', '-o', type=Path, default=Path('scripts/subsidies_inserts.sql'), help='Output SQL file')
    p.add_argument('--no-filter', dest='filter', action='store_false', help='Do not filter rows by the built-in car_categories mapping')
    args = p.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(2)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    generate(args.out, args.csv, filter_by_categories=args.filter)


if __name__ == '__main__':
    main()
