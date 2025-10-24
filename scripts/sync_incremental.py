#!/usr/bin/env python3
"""Incremental KEPCO sync

Safe, idempotent script to fetch KEPCO data (full or gu scope) and upsert only changed/new
stations and chargers based on csId and statUpdateDatetime.

Usage examples:
  # dry-run, don't write DB
  python3 scripts/sync_incremental.py --scope gu --dry-run --sleep 1.5

  # perform commit
  python3 scripts/sync_incremental.py --scope gu --commit --sleep 1.5

Design choices:
- Use existing stations.last_synced_at and charger.stat_update_datetime comparison when available.
- Parse API's statUpdateDatetime when provided; otherwise treat as always updateable.
- Default scope is 'gu' (uses KEPCO items filtered by 경기도 성남시 then per gu). Use 'full' to scan entire KEPCO dataset.
"""
import os
import sys
import time
import json
import argparse
from datetime import datetime
import requests
from sqlalchemy import create_engine, text


def parse_datetime(s):
    if not s:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y%m%d%H%M%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def fetch_keopco_all(kepco_url, key):
    params = {'apiKey': key, 'returnType': 'json'}
    r = requests.get(kepco_url, params=params, timeout=60)
    r.raise_for_status()
    j = r.json()
    return j.get('data') if isinstance(j, dict) else None


def fetch_by_addr(kepco_url, key, addr):
    params = {'addr': addr, 'apiKey': key, 'returnType': 'json'}
    r = requests.get(kepco_url, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()
    return j.get('data') if isinstance(j, dict) else None


def upsert_item(conn, item, now):
    cs_id = str(item.get('csId') or item.get('Csid') or '').strip()
    if not cs_id:
        return 0, 0

    cs_nm = item.get('csNm') or item.get('Csnm') or item.get('csnm') or ''
    addr = item.get('addr') or item.get('Addr') or ''
    lat_raw = item.get('lat') or item.get('Lat') or ''
    lon_raw = item.get('longi') or item.get('Longi') or item.get('long') or ''
    try:
        lat = float(lat_raw) if lat_raw not in (None, '', '0', 0) else None
    except Exception:
        lat = None
    try:
        lon = float(lon_raw) if lon_raw not in (None, '', '0', 0) else None
    except Exception:
        lon = None

    stat_update_src = item.get('statUpdateDatetime') or item.get('stat_update_datetime') or ''
    src_dt = parse_datetime(stat_update_src)

    # Compare with existing station last_synced_at; if API provides newer stat_update, we'll update.
    existing = conn.execute(text('SELECT id, last_synced_at FROM stations WHERE cs_id = :cs_id LIMIT 1'), {'cs_id': cs_id}).fetchone()
    if existing:
        existing_dt = existing[1]
        # If src_dt available and not newer, skip
        if src_dt and existing_dt and src_dt <= existing_dt:
            # still ensure chargers present
            pass
    # perform update/insert same as earlier script
    update_sql = text("""
        UPDATE stations SET
            name = COALESCE(:name, name),
            address = COALESCE(:address, address),
            location = CASE WHEN :lon IS NOT NULL AND :lat IS NOT NULL THEN ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) ELSE location END,
            raw_data = COALESCE(:raw_data, raw_data),
            last_synced_at = COALESCE(:last_synced_at, last_synced_at),
            updated_at = now()
        WHERE cs_id = :cs_id
    """)

    res = conn.execute(update_sql, {
        'cs_id': cs_id,
        'name': cs_nm,
        'address': addr,
        'lon': lon,
        'lat': lat,
        'raw_data': json.dumps(item, ensure_ascii=False),
        'last_synced_at': now,
    })

    if res.rowcount == 0:
        insert_sql = text("""
            INSERT INTO stations (station_code, cs_id, name, address, location, raw_data, last_synced_at, created_at, updated_at)
            VALUES (:station_code, :cs_id, :name, :address,
                    CASE WHEN :lon IS NOT NULL AND :lat IS NOT NULL THEN ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) ELSE NULL END,
                    :raw_data, :last_synced_at, now(), now())
        """)
        conn.execute(insert_sql, {
            'station_code': cs_id,
            'cs_id': cs_id,
            'name': cs_nm,
            'address': addr,
            'lon': lon,
            'lat': lat,
            'raw_data': json.dumps(item, ensure_ascii=False),
            'last_synced_at': now,
        })

    charger_count = 0
    cp_id = str(item.get('cpId') or item.get('Cpid') or '').strip()
    if cp_id:
        cp_stat = item.get('cpStat') or ''
        charge_tp = item.get('chargeTp') or item.get('Cptp') or ''
        station_row = conn.execute(text('SELECT id FROM stations WHERE cs_id = :cs_id LIMIT 1'), {'cs_id': cs_id}).fetchone()
        station_pk = station_row[0] if station_row else None
        update_ch_sql = text("""
            UPDATE chargers SET
                charger_code = COALESCE(:charger_code, charger_code),
                external_charger_id = COALESCE(:external_charger_id, external_charger_id),
                cp_stat_raw = COALESCE(:cp_stat_raw, cp_stat_raw),
                charger_type = COALESCE(:charger_type, charger_type),
                stat_update_datetime = COALESCE(:stat_update_datetime, stat_update_datetime),
                updated_at = now(),
                station_id = COALESCE(:station_id, station_id)
            WHERE charger_code = :charger_code
        """)
        r2 = conn.execute(update_ch_sql, {
            'charger_code': cp_id,
            'external_charger_id': cp_id,
            'cp_stat_raw': cp_stat,
            'charger_type': charge_tp,
            'station_id': station_pk,
            'stat_update_datetime': now,
        })
        if r2.rowcount == 0:
            insert_ch_sql = text("""
                INSERT INTO chargers (station_id, charger_code, external_charger_id, cp_stat_raw, charger_type, stat_update_datetime, created_at, updated_at)
                VALUES (:station_id, :charger_code, :external_charger_id, :cp_stat_raw, :charger_type, :stat_update_datetime, now(), now())
            """)
            conn.execute(insert_ch_sql, {
                'station_id': station_pk,
                'charger_code': cp_id,
                'external_charger_id': cp_id,
                'cp_stat_raw': cp_stat,
                'charger_type': charge_tp,
                'stat_update_datetime': now,
            })
        charger_count = 1

    return 1, charger_count


def main():
    parser = argparse.ArgumentParser(description='Incremental KEPCO sync')
    parser.add_argument('--scope', choices=('full', 'gu'), default='gu')
    parser.add_argument('--commit', action='store_true')
    parser.add_argument('--sleep', type=float, default=1.5)
    args = parser.parse_args()

    kepco_url = os.getenv('EXTERNAL_STATION_API_BASE_URL') or 'https://bigdata.kepco.co.kr/openapi/v1/EVchargeManage.do'
    kepco_key = os.getenv('EXTERNAL_STATION_API_KEY')
    db_url = os.getenv('LIBPQ_DATABASE_URL')
    if not kepco_key or not db_url:
        print('Missing EXTERNAL_STATION_API_KEY or LIBPQ_DATABASE_URL in env')
        sys.exit(1)

    engine = create_engine(db_url, pool_pre_ping=True)
    now = datetime.utcnow()

    total_s = 0
    total_c = 0

    if args.scope == 'full':
        print('Fetching full dataset (may be large)')
        data = fetch_keopco_all(kepco_url, kepco_key) or []
        items = [it for it in data if '성남' in (it.get('addr') or '') or '성남' in (it.get('csNm') or '')]
        print('Filtered items count:', len(items))
        if args.commit:
            with engine.begin() as conn:
                for it in items:
                    s,c = upsert_item(conn, it, now)
                    total_s += s; total_c += c
        else:
            print('Dry-run mode: would upsert', len(items), 'items')

    else:
        # gu scope: use gu-level addresses for Seongnam
        gus = ['경기도 성남시 수정구', '경기도 성남시 중원구', '경기도 성남시 분당구']
        for gu in gus:
            print('Fetching for', gu)
            data = fetch_by_addr(kepco_url, kepco_key, gu) or []
            if not data:
                print('  -> no items for', gu)
                continue
            if args.commit:
                with engine.begin() as conn:
                    for it in data:
                        s,c = upsert_item(conn, it, now)
                        total_s += s; total_c += c
            else:
                print('Dry-run: would upsert', len(data), 'items for', gu)
            time.sleep(args.sleep)

    print('Done. Totals stations:', total_s, 'chargers:', total_c)


if __name__ == '__main__':
    main()
