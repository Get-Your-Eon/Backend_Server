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
from datetime import datetime
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

# Addresses to query (use the list validated earlier)
ADDRESSES = [
    "경기도 성남시 분당구 분당로 50 (수내동, 분당구청) 실외주차장",
    "경기도 성남시 분당구 황새울로 273 (수내동) B1",
    "경기도 성남시 분당구 동판교로 122 (백현동, 백현마을2단지아파트) 203동 지하 2층 주차장",
    "경기도 성남시 분당구 판교역로 98 (백현동, 백현마을7단지아파트) 지상1층 주차장 주민센터 앞",
    "경기도 성남시 분당구 대왕판교로606번길 58 (삼평동, 판교푸르지오월드마크) 지하 4층 주차장",
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

    now = datetime.utcnow()

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


def fetch_and_store(address):
    params = {'addr': address, 'apiKey': KEPCO_KEY, 'returnType': 'json'}
    print('Requesting', address)
    r = requests.get(KEPCO_URL, params=params, timeout=20)
    r.raise_for_status()
    j = r.json()
    data = j.get('data') if isinstance(j, dict) else None
    if not data:
        print('  -> no data returned')
        return 0,0

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
    total_s = 0
    total_c = 0
    for addr in ADDRESSES:
        try:
            s,c = fetch_and_store(addr)
            total_s += s
            total_c += c
            time.sleep(0.5)
        except Exception as e:
            print('ERROR for', addr, e)
    print('Done. Total stations:', total_s, 'Total chargers:', total_c)

if __name__ == '__main__':
    main()
