import asyncio
import json
import sys
from app.core.config import settings
import httpx

import argparse

DEFAULT_STATION_ID = "5778"
DEFAULT_ADDR = "경기도 성남시 분당구 분당로 50 (수내동, 분당구청) 실외주차장"

async def main():
    kepco_url = settings.EXTERNAL_STATION_API_BASE_URL
    kepco_key = settings.EXTERNAL_STATION_API_KEY

    if not kepco_url or not kepco_key:
        print(json.dumps({"error": "KEPCO API settings missing", "EXTERNAL_STATION_API_BASE_URL": kepco_url is not None, "EXTERNAL_STATION_API_KEY": kepco_key is not None}))
        return

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(kepco_url, params={"addr": ADDR, "apiKey": kepco_key, "returnType": "json"}, timeout=30.0)
        except Exception as e:
            print(json.dumps({"error": "request_failed", "detail": str(e)}))
            return

    try:
        data = resp.json()
    except Exception as e:
        print(json.dumps({"error": "invalid_json", "status_code": resp.status_code, "text": resp.text[:1000]}))
        return

    if not isinstance(data, dict) or "data" not in data:
        print(json.dumps({"error": "unexpected_response", "keys": list(data.keys()) if isinstance(data, dict) else str(type(data))}))
        return

    items = data["data"]
    matched = [it for it in items if str(it.get("csId", "")) == STATION_ID]

    # If none matched by csId, try fuzzy match by address substring
    if not matched:
        for it in items:
            addr_field = it.get("addr", "")
            if ADDR.split()[0] in addr_field:
                matched.append(it)

    print(json.dumps({"queried_addr": ADDR, "station_id": STATION_ID, "kepco_status": resp.status_code, "matched_count": len(matched), "matched": matched}, ensure_ascii=False, indent=2, default=str))

def _parse_args():
    p = argparse.ArgumentParser(description="Query KEPCO API for a given station_id and address")
    p.add_argument("station_id", nargs="?", default=DEFAULT_STATION_ID, help="station id to filter (default 5778)")
    p.add_argument("addr", nargs="?", default=DEFAULT_ADDR, help="address to query KEPCO with")
    return p.parse_args()

if __name__ == '__main__':
    args = _parse_args()
    STATION_ID = str(args.station_id)
    ADDR = args.addr
    asyncio.run(main())
