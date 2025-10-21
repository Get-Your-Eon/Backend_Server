#!/usr/bin/env python3
"""
Normalize subsidy.csv: remove first column (차종), add 모델그룹 column populated
from provided car_categories mapping using model name matching.

Backs up original file to subsidy.csv.bak and writes normalized CSV to subsidy.csv
with header: 제조사,모델그룹,모델명,국비(만원),지방비(만원),보조금(만원)

This script uses simple normalization rules and an alias map to match common
variants (e.g. '코나 일렉트릭' -> '코나 EV'). Rows that cannot be matched will
be written with an empty 모델그룹 and reported to stdout.
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
    """Return a cleaned version used for matching only (does NOT modify model_name output).
    Cleans: remove parenthesis content, lowercases, collapses spaces, removes common prefixes like '더', '더뉴', 'new', 'the'.
    Also map '일렉트릭' -> 'EV' for matching purposes.
    """
    if s is None:
        return ''
    s = s.strip()
    # remove parenthesis content like (단종)
    s = re.sub(r"\([^)]*\)", '', s)
    # collapse spaces and lower
    s = re.sub(r"\s+", ' ', s)
    s = s.strip()
    s_lower = s.lower()
    # remove common prefixes '더', '더뉴', 'new', 'the' when attached
    s_lower = re.sub(r'^(더뉴|더\s+뉴|더|new|the)\s*', '', s_lower)
    # normalize some tokens
    s_lower = s_lower.replace('일렉트릭', 'ev')
    s_lower = s_lower.replace('일렉트릭', 'ev')
    s_lower = s_lower.replace('*', '')
    s_lower = s_lower.strip()
    return s_lower


def find_model_group(manufacturer: str, model_name: str) -> str:
    # build a matching-only normalized string
    mname_norm = normalize_text(model_name)

    # check alias map first (alias keys are already lower)
    for k, v in alias_map.items():
        if k in mname_norm:
            return v

    allowed = car_categories.get(manufacturer)
    if not allowed:
        return ''

    # try startswith match (prefer longer group names)
    sorted_allowed = sorted(list(allowed), key=lambda s: -len(s))
    # try startswith on normalized strings
    for g in sorted_allowed:
        if mname_norm.startswith(g.lower()):
            return g

    # try contains (word boundary) on normalized strings
    for g in sorted_allowed:
        pattern = r'\b' + re.escape(g.lower()) + r'\b'
        if re.search(pattern, mname_norm):
            return g

    # try more relaxed: check if any token of the allowed group appears in name
    name_tokens = re.findall(r"[\w]+", mname_norm)
    for g in sorted_allowed:
        g_tokens = re.findall(r"[\w]+", g.lower())
        # if last token of group (e.g., '5' in '아이오닉5') appears in name tokens
        if any(t in name_tokens for t in g_tokens):
            return g

    # try first token heuristic (after removing prefixes)
    first_token = mname_norm.split()[0] if mname_norm else ''
    for g in sorted_allowed:
        if g.lower().split()[0] == first_token:
            return g

    return ''


def main():
    root = Path.cwd()
    csv_path = root / 'subsidy.csv'
    if not csv_path.exists():
        print('subsidy.csv not found in workspace root', file=sys.stderr)
        sys.exit(2)

    bak = root / 'subsidy.csv.bak'
    if not bak.exists():
        csv_path.replace(bak)
        # restore original to work on
        bak.replace(csv_path)
    else:
        # if backup already exists, still read original
        pass

    rows = []
    with csv_path.open('r', encoding='utf-8') as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        for i, r in enumerate(reader, start=2):
            if len(r) < 6:
                # try to skip or pad
                print(f'line {i} has {len(r)} columns, skipping', file=sys.stderr)
                continue
            # original columns: 차종,제조사,모델명,국비,지방비,보조금
            manu = r[1].strip()
            model_name = r[2].strip()
            nat = r[3].strip()
            loc = r[4].strip()
            tot = r[5].strip()
            mg = find_model_group(manu, model_name)
            rows.append((manu, mg, model_name, nat, loc, tot))

    out_path = csv_path
    with out_path.open('w', encoding='utf-8', newline='') as out:
        writer = csv.writer(out)
        writer.writerow(['제조사', '모델그룹', '모델명', '국비(만원)', '지방비(만원)', '보조금(만원)'])
        for r in rows:
            writer.writerow(r)

    # report unmatched
    unmatched = [r for r in rows if r[1] == '']
    print(f'Wrote {len(rows)} rows to {out_path} (unmatched model_group: {len(unmatched)})')
    if unmatched:
        print('Sample unmatched rows (manufacturer, model_name):')
        for m, mg, mn, *_ in unmatched[:20]:
            print('-', m, '|', mn)


if __name__ == '__main__':
    main()
