#!/usr/bin/env python3
"""Backfill stations and chargers from KEPCO API into the local DB.

Usage:
  # Ensure env vars are set (or use defaults below)
  export LIBPQ_DATABASE_URL="postgresql://..." \
         EXTERNAL_STATION_API_BASE_URL="https://bigdata.kepco.co.kr/openapi/v1/EVchargeManage.do" \
         EXTERNAL_STATION_API_KEY="..."
  python3 scripts/backfill_kepco.py

This script is intentionally synchronous and conservative: it upserts stations and chargers
using INSERT ... ON CONFLICT. It also stores the raw API payload into stations.raw_data.
"""
import os
import sys
import json
import time
from datetime import datetime, timezone
import requests
from sqlalchemy import create_engine, text

# Configuration (read from env when possible)
DB_URL = os.getenv('LIBPQ_DATABASE_URL') or os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_SYNC')
KEPCO_URL = os.getenv('EXTERNAL_STATION_API_BASE_URL') or 'https://bigdata.kepco.co.kr/openapi/v1/EVchargeManage.do'
KEPCO_KEY = os.getenv('EXTERNAL_STATION_API_KEY') or os.getenv('KEPCO_API_KEY')

if not DB_URL:
    print('ERROR: No DB URL provided. Set LIBPQ_DATABASE_URL or DATABASE_URL environment variable.')
    sys.exit(1)
if not KEPCO_KEY:
    print('ERROR: No KEPCO API key provided. Set EXTERNAL_STATION_API_KEY or KEPCO_API_KEY environment variable.')
    sys.exit(1)

# Addresses to query: use gu-level queries for 성남시 to reduce number of API calls and load.
# We will query each 구 (district) of 성남시 and optionally expand to dong level later.
ADDRESSES = [
    "경기도 성남시 수정구",
    "경기도 성남시 중원구",
    "경기도 성남시 분당구",
]

# Create synchronous SQLAlchemy engine
engine = create_engine(DB_URL, pool_pre_ping=True)

def upsert_station_and_charger(conn, item):
    """Upsert a station and a charger from a KEPCO item dict."""
    cs_id = str(item.get('csId') or item.get('Csid') or '').strip()
    if not cs_id:
        return 0,0

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

    now = datetime.now(timezone.utc)

    # Upsert station
    # Note: the stations table uses `last_synced_at` for timestamp of sync
    station_sql = text("""
        INSERT INTO stations (cs_id, name, address, location, raw_data, last_synced_at, updated_at)
        VALUES (:cs_id, :name, :address,
                CASE WHEN :lon IS NOT NULL AND :lat IS NOT NULL THEN ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) ELSE NULL END,
                :raw_data, :last_synced_at, now())
        ON CONFLICT (cs_id) DO UPDATE SET
            name = COALESCE(EXCLUDED.name, stations.name),
            address = COALESCE(EXCLUDED.address, stations.address),
            location = COALESCE(EXCLUDED.location, stations.location),
            raw_data = COALESCE(EXCLUDED.raw_data, stations.raw_data),
            last_synced_at = COALESCE(EXCLUDED.last_synced_at, stations.last_synced_at),
            updated_at = now()
    """)

    # Try UPDATE first; if no row updated then INSERT. This avoids requiring a unique index on cs_id.
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
        'last_synced_at': now
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
            'last_synced_at': now
        })

    # Upsert charger if cpId present
    cp_id = str(item.get('cpId') or item.get('Cpid') or '').strip()
    charger_count = 0
    if cp_id:
        cp_nm = item.get('cpNm') or ''
        cp_stat = item.get('cpStat') or ''
        charge_tp = item.get('chargeTp') or item.get('Cptp') or ''
        # resolve station.id for foreign key
        station_row = conn.execute(text("SELECT id FROM stations WHERE cs_id = :cs_id LIMIT 1"), {'cs_id': cs_id}).fetchone()
        station_pk = station_row[0] if station_row else None

        # Update existing charger, otherwise insert
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
            'stat_update_datetime': now
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
                'stat_update_datetime': now
            })
        charger_count = 1

    return 1, charger_count


def fetch_only(address, max_retries=2):
    """Fetch items from KEPCO API for an address and return list of items (no DB writes).
    Retries a small number of times on transient errors.
    """
    params = {'addr': address, 'apiKey': KEPCO_KEY, 'returnType': 'json'}
    tries = 0
    while True:
        tries += 1
        try:
            print('Requesting', address)
            r = requests.get(KEPCO_URL, params=params, timeout=20)
            r.raise_for_status()
            j = r.json()
            data = j.get('data') if isinstance(j, dict) else None
            if not data:
                print('  -> no data returned')
                return []
            return data
        except Exception as e:
            print(f'  -> request error (attempt {tries}):', e)
            if tries > max_retries:
                print('  -> giving up for', address)
                return []
            time.sleep(1 + tries)


def fetch_and_store(address):
    """Existing behavior: fetch and store into DB. Kept separate so dry-run can use fetch_only."""
    data = fetch_only(address)
    if not data:
        return 0, 0

    with engine.begin() as conn:
        stations_inserted = 0
        chargers_inserted = 0
        for item in data:
            s, c = upsert_station_and_charger(conn, item)
            stations_inserted += s
            chargers_inserted += c
        print(f'  -> inserted/updated stations: {stations_inserted}, chargers: {chargers_inserted}')
        return stations_inserted, chargers_inserted


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Backfill KEPCO data (성남시)')
    parser.add_argument('--dry-run', action='store_true', help='Fetch only and report unique stations (no DB writes)')
    parser.add_argument('--sleep', type=float, default=1.0, help='Seconds to sleep between address requests')
    parser.add_argument('--commit', action='store_true', help='Actually perform DB writes (default is to not commit unless set)')
    args = parser.parse_args()

    # If dry-run, just fetch and deduplicate cs_id to estimate load
    if args.dry_run and not args.commit:
        print('DRY RUN: fetching data for addresses (no DB writes)')
        found_cs = set()
        total_items = 0
        for addr in ADDRESSES:
            try:
                items = fetch_only(addr)
                total_items += len(items)
                for it in items:
                    cs = str(it.get('csId') or it.get('Csid') or '').strip()
                    if cs:
                        found_cs.add(cs)
                time.sleep(args.sleep)
            except Exception as e:
                print('ERROR fetching', addr, e)
        print('DRY RUN RESULT: addresses:', len(ADDRESSES), 'total items fetched:', total_items,
              'unique stations (cs_id):', len(found_cs))
        print('Sample cs_ids:', list(found_cs)[:20])
        return

    # Otherwise perform commit mode (requires --commit flag)
    if not args.commit:
        print('No --commit flag provided. To perform DB writes pass --commit. Use --dry-run to estimate first.')
        return

    # Commit mode: perform backup prompt and then run writes with throttling
    print('COMMIT MODE: will write to DB. Running addresses:', ADDRESSES)
    total_s = 0
    total_c = 0
    for addr in ADDRESSES:
        try:
            s, c = fetch_and_store(addr)
            total_s += s
            total_c += c
            time.sleep(args.sleep)
        except Exception as e:
            print('ERROR for', addr, e)
    print('Done. Total stations:', total_s, 'Total chargers:', total_c)

if __name__ == '__main__':
    main()
