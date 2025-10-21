#!/usr/bin/env python3
"""
Repair subsidy.csv when columns were shifted or manufacturer/model_group are missing.

Creates subsidy_repaired.csv (backup original to subsidy.csv.orig if not present).
Heuristics:
 - If 제조사 value matches a known model_group, map it back to its manufacturer.
 - If 모델그룹 is populated and matches known model_group, set 제조사 accordingly.
 - If 제조사 missing, try to infer manufacturer from 모델명 using model_group tokens and alias_map.
 - If 모델그룹 missing, use manufacturer+model_name heuristics (similar to normalize_subsidy_csv.find_model_group).

This is a non-destructive recovery step to be used before generating SQL.
"""
from pathlib import Path
import csv
import re
import sys


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

# alias rules: substring (lower) -> canonical model_group
alias_map = {
    '코나 일렉트릭': '코나 EV',
    '코나일렉트릭': '코나 EV',
    'the all-new kia niro ev': 'Niro EV',
    'polestar 4 long range': 'Polestar 4',
    'ex30 single motor': 'EX30',
    'byd seal': 'SEAL',
    'atto3': 'ATTO 3',
    'atto 3': 'ATTO 3',
    'byd atto': 'ATTO 3',
}


def normalize_text(s: str) -> str:
    if s is None:
        return ''
    s = s.strip()
    s = re.sub(r"\([^)]*\)", '', s)
    s = re.sub(r"\s+", ' ', s)
    s = s.strip()
    s_lower = s.lower()
    s_lower = re.sub(r'^(더뉴|더\s+뉴|더|new|the)\s*', '', s_lower)
    s_lower = s_lower.replace('일렉트릭', 'ev')
    s_lower = s_lower.replace('*', '')
    s_lower = s_lower.strip()
    return s_lower


def model_group_to_manufacturer_map():
    m = {}
    for manu, groups in car_categories.items():
        for g in groups:
            m[g.lower()] = manu
    return m


def find_model_group(manufacturer: str, model_name: str) -> str:
    mname_norm = normalize_text(model_name)
    manu_allowed = car_categories.get(manufacturer) if manufacturer else None
    # alias map
    for k, v in alias_map.items():
        if k in mname_norm:
            return v

    if manu_allowed:
        sorted_allowed = sorted(list(manu_allowed), key=lambda s: -len(s))
        for g in sorted_allowed:
            if mname_norm.startswith(g.lower()):
                return g
        for g in sorted_allowed:
            pattern = r'\b' + re.escape(g.lower()) + r'\b'
            if re.search(pattern, mname_norm):
                return g
        name_tokens = re.findall(r"[\w]+", mname_norm)
        for g in sorted_allowed:
            g_tokens = re.findall(r"[\w]+", g.lower())
            if any(t in name_tokens for t in g_tokens):
                return g

    return ''


def main():
    root = Path.cwd()
    csv_path = root / 'subsidy.csv'
    if not csv_path.exists():
        print('subsidy.csv not found', file=sys.stderr)
        sys.exit(2)

    orig = root / 'subsidy.csv.orig'
    if not orig.exists():
        # make a copy backup
        csv_path.replace(orig)
        # restore working file from original copy
        orig.replace(csv_path)

    mg_to_manu = model_group_to_manufacturer_map()

    rows = []
    with csv_path.open('r', encoding='utf-8') as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        for i, r in enumerate(reader, start=2):
            if len(r) < 6:
                print(f'line {i} has {len(r)} columns, skipping', file=sys.stderr)
                continue
            manu = r[0].strip()
            mg = r[1].strip()
            model_name = r[2].strip()
            nat = r[3].strip()
            loc = r[4].strip()
            tot = r[5].strip()

            repaired = False

            # if manu seems to be a model_group (e.g., 'GV60'), map back
            if manu and manu.lower() in mg_to_manu:
                manu = mg_to_manu[manu.lower()]
                repaired = True

            # if mg present but manu missing or invalid, set manu from mg
            if mg and mg.lower() in mg_to_manu and (not manu or manu not in car_categories):
                manu = mg_to_manu[mg.lower()]
                repaired = True

            # if manu empty or not in mapping, try to infer from model_name
            if (not manu or manu not in car_categories):
                # try to find any model_group token in model_name
                mn_norm = normalize_text(model_name)
                found = None
                # check alias_map first
                for k, v in alias_map.items():
                    if k in mn_norm:
                        found = v
                        break
                if not found:
                    for g_lower, mfr in mg_to_manu.items():
                        if g_lower in mn_norm:
                            found = g_lower
                            manu = mfr
                            break
                if found and not manu:
                    manu = mg_to_manu.get(found) or manu
                    repaired = True

            # if model_group empty, attempt to infer using manufacturer+model_name
            if not mg and manu and manu in car_categories:
                inferred = find_model_group(manu, model_name)
                if inferred:
                    mg = inferred
                    repaired = True

            rows.append((manu or '', mg or '', model_name, nat, loc, tot, repaired))

    out_path = root / 'subsidy_repaired.csv'
    with out_path.open('w', encoding='utf-8', newline='') as out:
        writer = csv.writer(out)
        writer.writerow(['제조사', '모델그룹', '모델명', '국비(만원)', '지방비(만원)', '보조금(만원)'])
        for r in rows:
            writer.writerow(r[:6])

    total = len(rows)
    repaired_count = sum(1 for r in rows if r[6])
    unmatched = [r for r in rows if (not r[0] or not r[1])]
    print(f'Wrote {total} rows to {out_path} (repaired: {repaired_count}, unmatched manufacturer/model_group: {len(unmatched)})')
    if unmatched:
        print('Sample unmatched rows (manufacturer, model_group, model_name):')
        for m, mg, mn, *_ in unmatched[:20]:
            print('-', m, '|', mg, '|', mn)


if __name__ == '__main__':
    main()
