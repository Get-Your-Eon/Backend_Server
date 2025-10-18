from typing import List, Optional, Dict, Any
import asyncio
import math
import httpx
import logging
import re
from app.core.config import settings
from app.redis_client import get_cache, set_cache, get_redis_client
from app.schemas.station import StationSummary, StationDetail, ChargerDetail
from app.repository.station import get_nearby_stations_db, upsert_stations_and_chargers
from app.db.database import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio


# logger for this module
logger = logging.getLogger("app.services.station_service")


class ExternalAPIError(Exception):
    pass


# External status mapping (numeric code -> readable status)
STATUS_CODE_MAP = {
    0: "UNKNOWN",
    1: "CHARGING",
    2: "AVAILABLE",
    3: "OUT_OF_ORDER",
    4: "MAINTENANCE",
    5: "RESERVED",
}


def _map_status(code: Any) -> Optional[str]:
    if code is None:
        return None
    try:
        ival = int(code)
        return STATUS_CODE_MAP.get(ival, f"UNKNOWN_{ival}")
    except Exception:
        return str(code)


def _normalize_connector_types(raw_val: Any) -> List[str]:
    # Accept a list, comma/pipe/semicolon-separated string, or single value
    if raw_val is None:
        return []
    if isinstance(raw_val, list):
        out = [str(x).strip() for x in raw_val if str(x).strip()]
        return out
    s = str(raw_val)
    if not s:
        return []
    # split on common delimiters
    parts = [p.strip() for p in re.split(r"[,|;]", s) if p.strip()]
    return parts


def _extract_coords_from_raw(raw: Dict[str, Any]) -> Optional[tuple]:
    # try common keys
    lat_keys = ("y", "lat", "latitude", "latitudeValue")
    lon_keys = ("x", "lon", "longitude", "longitudeValue")
    lat = None
    lon = None
    for k in lat_keys:
        if k in raw and raw.get(k) is not None:
            try:
                lat = float(raw.get(k))
                break
            except Exception:
                continue
    for k in lon_keys:
        if k in raw and raw.get(k) is not None:
            try:
                lon = float(raw.get(k))
                break
            except Exception:
                continue
    if lat is None or lon is None:
        return None
    return (lat, lon)


class StationService:
    """
    외부 충전소 API와 통신하는 서비스 계층입니다.
    """

    def __init__(self):
        self.base_url = settings.EXTERNAL_STATION_API_BASE_URL
        self.api_key = settings.EXTERNAL_STATION_API_KEY
        self.auth_type = settings.EXTERNAL_STATION_API_AUTH_TYPE
        self.header_name = settings.EXTERNAL_STATION_API_KEY_HEADER_NAME
        self.timeout = settings.EXTERNAL_STATION_API_TIMEOUT_SECONDS

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key and self.auth_type == "header":
            headers[self.header_name] = self.api_key
        return headers

    def _build_params(self) -> Dict[str, str]:
        params: Dict[str, str] = {}
        if self.api_key and self.auth_type == "query":
            params["api_key"] = self.api_key
        return params

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if not self.base_url:
            raise ExternalAPIError("External station API base URL is not configured")

        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = self._build_headers()
        base_params = self._build_params()
        if params:
            base_params.update(params)

        # Simple retry with backoff
        retries = 2
        backoff = 0.5
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url, headers=headers, params=base_params)
                    if resp.status_code == 200:
                        return resp.json()
                    # map 429/5xx to ExternalAPIError
                    if resp.status_code == 429:
                        raise ExternalAPIError("Rate limited by external API")
                    if 500 <= resp.status_code < 600:
                        raise ExternalAPIError(f"External server error: {resp.status_code}")
                    # other 4xx -> treat as not found / bad request
                    resp.raise_for_status()
            except (httpx.RequestError, ExternalAPIError) as e:
                if attempt < retries:
                    await asyncio.sleep(backoff * (2 ** attempt))
                    continue
                raise

    async def _post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """POST 요청을 보냅니다. path는 base_url에 이어 붙일 경로입니다."""
        if not self.base_url:
            raise ExternalAPIError("External station API base URL is not configured")

        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/') }"
        headers = self._build_headers()
        base_params = self._build_params()

        retries = 2
        backoff = 0.5
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, headers=headers, params=base_params, json=json)
                    # Log status and truncated body for debugging (do not log headers or secrets)
                    try:
                        body_text = resp.text
                    except Exception:
                        body_text = "<unreadable>"
                    truncated = body_text[:2000] + ("...[truncated]" if len(body_text) > 2000 else "")
                    logger.info("External POST %s status=%s body=%s", url, resp.status_code, truncated)

                    if resp.status_code == 200:
                        return resp.json()
                    if resp.status_code == 429:
                        raise ExternalAPIError("Rate limited by external API")
                    if 500 <= resp.status_code < 600:
                        raise ExternalAPIError(f"External server error: {resp.status_code}")
                    resp.raise_for_status()
            except (httpx.RequestError, ExternalAPIError) as e:
                if attempt < retries:
                    await asyncio.sleep(backoff * (2 ** attempt))
                    continue
                raise

    async def search_stations(self, lat: "str|float", lon: "str|float", radius_m: int = 1000, page: int = 1, limit: int = 20) -> List[StationSummary]:
        # 허용: lat/lon이 문자열로 올 수 있으므로 안전하게 파싱
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except Exception:
            raise ExternalAPIError("Invalid latitude/longitude values")
        cache_key = f"stations:near:{lat_f:.4f}:{lon_f:.4f}:{radius_m}:{page}:{limit}"
        cached = await get_cache(cache_key)
        if cached:
            return [StationSummary(**s) for s in cached]

        # 1) DB 조회 (PostGIS 사용 가능 시 더 효율적인 쿼리로 대체)
        async with AsyncSessionLocal() as session:
            try:
                db_results = await get_nearby_stations_db(session, lat_f, lon_f, radius_m, limit=limit, offset=(page-1)*limit)
                if db_results:
                    await set_cache(cache_key, db_results)
                    return [StationSummary(**s) for s in db_results]
            except Exception:
                # DB 에러가 나면 무시하고 외부 API 호출로 fallback
                pass

        # 외부 사이트(실제 chargeinfo 페이지)의 JS를 분석한 결과, 검색은
        # POST /ws/chargePoint/curChargePoint (또는 searchChargePoint)로
        # cond JSON 객체를 전송하는 방식입니다. 여기서는 단순히 지도 중심
        # + radius를 이용해 bounding box를 계산하여 cond를 구성합니다.

        # If external API is not configured, avoid calling it and return empty list.
        # This prevents a hard 502 when deployment lacks external API settings.
        if not self.base_url:
            logger.warning("External station API base URL is not configured; returning fallback results (empty or DB results)")
            # at this point DB lookup was already attempted above; return empty list
            await set_cache(cache_key, [])
            return []

        # 위도/경도 -> 각도 차 계산 (대략 1 deg latitude ~= 111km)
        delta_lat = radius_m / 111000.0
        # 경도는 위도에 따라 달라짐
        try:
            delta_lon = radius_m / (111000.0 * max(0.000001, math.cos(math.radians(lat_f))))
        except Exception:
            delta_lon = radius_m / 111000.0

        maxLat = lat_f + delta_lat
        minLat = lat_f - delta_lat
        maxLng = lon_f + delta_lon
        minLng = lon_f - delta_lon

        cond = {
            "maxLat": maxLat,
            "minLat": minLat,
            "maxLng": maxLng,
            "minLng": minLng,
            "lat": lat_f,
            "lon": lon_f,
            # 기본적으로 검색 텍스트/필터가 없으면 searchStatus=false
            "searchStatus": False,
            # Render에서 제공된 API 키(팀원이 말한 serviceKey)가 필요한 경우 body에 포함
            # (일부 실사용 API는 serviceKey를 POST body에 요구함)
            **({"serviceKey": self.api_key} if self.api_key else {}),
            # 페이지 정보 (팀원 정보에 따르면 pageNumber가 필수)
            "pageNumber": int(page),
            "pageSize": int(limit)
        }

        # POST 형식으로 충전소 목록을 요청
        # To prevent thundering herd, acquire a simple redis lock per cache_key
        lock_key = f"lock:{cache_key}"
        redis_client = await get_redis_client()
        have_lock = False
        if redis_client:
            try:
                # setnx with short TTL
                have_lock = await redis_client.set(lock_key, "1", nx=True, ex=10)
            except Exception:
                have_lock = False

        payload = None
        if not have_lock:
            # someone else is likely populating cache; wait briefly then check cache again
            await asyncio.sleep(0.5)
            cached2 = await get_cache(cache_key)
            if cached2:
                return [StationSummary(**s) for s in cached2]

        payload = await self._post('/ws/chargePoint/curChargePoint', json=cond)

        # Log returned station payload (truncated) for debugging charger specs
        try:
            import json as _json
            raw_payload_text = _json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)
        except Exception:
            raw_payload_text = str(payload)
        try:
            logger.info("curChargePoint payload for cache=%s (lat=%s lon=%s): %s", cache_key, lat_f, lon_f, raw_payload_text[:2000])
        except Exception:
            # Defensive: if any local variable is not available or logging fails, don't crash the request
            logger.debug("Skipping curChargePoint debug log due to missing context or logging error.")

        items = []
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get('result') or payload.get('data') or []

        summaries: List[StationSummary] = []
        cp_key_list: List[str] = []
        for it in items:
            bid = it.get('bid') or ''
            cpId = it.get('cpId') or it.get('cpid') or it.get('cp_id') or ''
            cp_key = f"P{bid}{cpId}"
            cp_key_list.append(cp_key)
            lat_val = it.get('lat') or it.get('latitude') or it.get('y') or 0.0
            lon_val = it.get('lon') or it.get('longitude') or it.get('x') or 0.0

            name = it.get('cpName') or it.get('cp_name') or it.get('station_name') or ''
            address = it.get('addr') or it.get('roadName') or it.get('address')

            # 거리 정보는 외부에서 '0.71' 같은 소수(km) 또는 정수(미터)로 올 수 있으므로
            # 안전하게 정수(미터)로 변환합니다. 소수값이 10보다 작으면 km로 간주하고 *1000 변환.
            raw_dis = it.get('dis') or it.get('distance') or it.get('distance_m')
            distance_m = None
            if raw_dis is not None:
                try:
                    d = float(raw_dis)
                    if d < 10:
                        # 보통 0.71 처럼 올 경우 km 단위로 보정
                        distance_m = int(round(d * 1000))
                    else:
                        # 이미 미터 단위로 온 경우
                        distance_m = int(round(d))
                except Exception:
                    distance_m = None

            summaries.append(StationSummary(
                id=f"{bid}_{cpId}",
                name=name,
                address=address,
                lat=float(lat_val) if lat_val is not None else 0.0,
                lon=float(lon_val) if lon_val is not None else 0.0,
                distance_m=distance_m,
                charger_count=None
            ))

        # 충전기 상세를 얻어 각 충전소의 충전기 수를 채웁니다.
        try:
            if cp_key_list:
                charger_resp = await self._post('/ws/charger/curCharger', json={"cpKeyList": cp_key_list})
                # charger_resp는 리스트로 반환되는 것이 JS에서 관찰됨
                if isinstance(charger_resp, list):
                    # 각 항목에 대해 bid+cpId 조합으로 매핑
                    counts: Dict[str, int] = {}
                    for ch in charger_resp:
                        bid = ch.get('bid') or ''
                        cpId = ch.get('cpId') or ch.get('cpid') or ''
                        key = f"{bid}_{cpId}"
                        counts[key] = counts.get(key, 0) + 1
                    for s in summaries:
                        s.charger_count = counts.get(s.id, 0)
        except Exception:
            # 충전기 조회 실패는 전체 검색 실패로 연결하지 않음
            pass

        # persist results to DB (best-effort)
        try:
            async with AsyncSessionLocal() as session:
                await upsert_stations_and_chargers(session, [s.dict() for s in summaries])
        except Exception:
            pass

        await set_cache(cache_key, [s.dict() for s in summaries])
        if redis_client and have_lock:
            try:
                await redis_client.delete(lock_key)
            except Exception:
                pass
        return summaries

    async def get_station_detail(self, station_id: str) -> StationDetail:
        # Normalize incoming station identifier into an external cp_key used by the provider
        # Acceptable incoming forms:
        # - cp_key already provided (starts with 'P')
        # - canonical id returned from search: "{bid}_{cpId}"
        # - fallback: raw id -> prepend 'P'
        if isinstance(station_id, str) and station_id.startswith('P'):
            cp_key = station_id
        elif '_' in station_id:
            bid, cpId = station_id.split('_', 1)
            cp_key = f"P{bid}{cpId}"
        else:
            # unknown format: assume it's a cpId or short id and prepend 'P'
            cp_key = f"P{station_id}"

        # Use normalized cp_key as cache key to avoid collisions when different station_id
        # representations are passed in by clients.
        cache_key = f"station:detail:{cp_key}"
        cached = await get_cache(cache_key)
        if cached:
            return StationDetail(**cached)

        # 먼저 충전소 기본 정보를 가져옵니다. curChargePoint에 cpKeyList로 요청하면
        # 해당 충전소(들)의 정보가 반환됩니다.
        cond = {"cpKeyList": [cp_key], "searchStatus": False}
        payload = await self._post('/ws/chargePoint/curChargePoint', json=cond)

        item = None
        if isinstance(payload, list) and len(payload) > 0:
            item = payload[0]
        elif isinstance(payload, dict):
            # 일부 응답은 {result: [...]} 구조일 수 있음
            arr = payload.get('result') or payload.get('data') or []
            if arr:
                item = arr[0]

        if not item:
            raise ExternalAPIError('Station not found from external API')

        # Ensure the returned station payload actually matches the requested cp_key
        # Some external endpoints may return a fallback/default record when cp_key is not found.
        # If the returned bid/cpId do not match the requested cp_key, treat as not found.
        returned_bid = item.get('bid') or ''
        returned_cpId = item.get('cpId') or item.get('cpid') or ''
        # requested bid/cpId derived from cp_key: cp_key = 'P{bid}{cpId}'
        req = cp_key[1:]
        mismatch_detected = False
        if req and not req.endswith(returned_cpId):
            # mismatch: sometimes the station endpoint returns a generic/fallback record
            # while charger endpoint contains the actual cpId we asked for. Attempt to
            # find station info from charger_payload if possible.
            try:
                ch_resp = await self._post('/ws/charger/curCharger', json={"cpKeyList": [cp_key]})
            except Exception:
                ch_resp = None

            found_station_info = None
            if isinstance(ch_resp, list):
                for ch in ch_resp:
                    if (ch.get('bid', '') + (ch.get('cpId') or ch.get('cpid') or '')) == req:
                        # found matching charger record that corresponds to our requested cp_key
                        found_station_info = {
                            'bid': ch.get('bid'),
                            'cpId': ch.get('cpId') or ch.get('cpid')
                        }
                        break

            if found_station_info:
                # re-query station endpoint with the found charger-derived cpId to get accurate station info
                new_cp_key = f"P{found_station_info['bid']}{found_station_info['cpId']}"
                try:
                    new_payload = await self._post('/ws/chargePoint/curChargePoint', json={"cpKeyList": [new_cp_key], "searchStatus": False})
                    new_item = None
                    if isinstance(new_payload, list) and len(new_payload) > 0:
                        new_item = new_payload[0]
                    elif isinstance(new_payload, dict):
                        arr = new_payload.get('result') or new_payload.get('data') or []
                        if arr:
                            new_item = arr[0]
                    if new_item:
                        item = new_item
                        cp_key = new_cp_key
                        cache_key = f"station:detail:{cp_key}"
                    else:
                        # fallback to minimal override if re-query failed
                        item['bid'] = found_station_info['bid']
                        item['cpId'] = found_station_info['cpId']
                except Exception:
                    # re-query failed; still fallback to minimal override
                    item['bid'] = found_station_info['bid']
                    item['cpId'] = found_station_info['cpId']
                mismatch_detected = True
            else:
                logger.warning("Requested cp_key=%s but external returned bid=%s cpId=%s; no matching charger record found; treating as not found", cp_key, returned_bid, returned_cpId)
                # Try a last-resort fallback: if charger endpoint contains entries that match the requested cpId
                try:
                    cp_found = None
                    if isinstance(ch_resp, list):
                        for ch in ch_resp:
                            # compare using parsed cpId from incoming station_id
                            if '_' in station_id:
                                _, requested_cpId = station_id.split('_', 1)
                            else:
                                requested_cpId = station_id
                            if (ch.get('cpId') or ch.get('cpid') or '') == requested_cpId:
                                cp_found = ch
                                break
                    if cp_found:
                        # build chargers list from ch_resp entries that match requested_cpId
                        chargers = []
                        for c in ch_resp:
                            if (c.get('cpId') or c.get('cpid') or '') == requested_cpId:
                                charger_id = str(c.get('chargerId') or c.get('id') or c.get('csId') or c.get('csId'))
                                numeric_status = c.get('csStatCode') if 'csStatCode' in c else c.get('status')
                                chargers.append(ChargerDetail(
                                    id=charger_id,
                                    station_id=station_id,
                                    connector_types=[c.get('connectorType') or c.get('connector') or ''],
                                    max_power_kw=c.get('outputKw') or c.get('output') or None,
                                    status=str(numeric_status) if numeric_status is not None else None,
                                    manufacturer=c.get('maker') or c.get('manufacturer'),
                                    model=c.get('model') or c.get('modelNm'),
                                    bid=c.get('bid'),
                                    cpId=c.get('cpId') or c.get('cpid'),
                                    charger_code=c.get('csId'),
                                    cs_cat_code=c.get('csCatCode'),
                                    info_coll_date=c.get('infoCollDate'),
                                    status_code=c.get('csStatCode'),
                                    ch_start_date=c.get('chStartDate'),
                                    last_ch_start_date=c.get('lastChStartDate'),
                                    last_ch_end_date=c.get('lastChEndDate'),
                                    updated_at=c.get('updateDate'),
                                    raw=c
                                ))
                        # avoid referencing undefined extra_info here; use empty dict
                        fallback_detail = StationDetail(
                            id=station_id,
                            name=item.get('cpName') or f"Station {station_id}",
                            address=item.get('addr') or None,
                            lat=0.0,
                            lon=0.0,
                            extra_info={'fallback_from_chargers': True},
                            chargers=[c.dict() if hasattr(c, 'dict') else c for c in chargers]
                        )
                        try:
                            await set_cache(cache_key, fallback_detail.dict())
                        except Exception:
                            logger.debug("Failed to set cache for fallback %s", cache_key)
                        return fallback_detail
                except Exception:
                    pass
                raise ExternalAPIError('Station not found from external API')

        # charger 상세 조회
        chargers: List[ChargerDetail] = []
        try:
            ch_resp = await self._post('/ws/charger/curCharger', json={"cpKeyList": [cp_key]})
            logger.info("curCharger response for %s: %s", cp_key, str(ch_resp)[:2000])
            if isinstance(ch_resp, list):
                    for c in ch_resp:
                        charger_id = str(c.get('chargerId') or c.get('id') or c.get('csId') or c.get('csId'))
                        numeric_status = c.get('csStatCode') if 'csStatCode' in c else c.get('status')
                        connectors = _normalize_connector_types(c.get('connectorType') or c.get('connector') or '')
                        chargers.append(ChargerDetail(
                            id=charger_id,
                            station_id=station_id,
                            connector_types=connectors,
                            max_power_kw=c.get('outputKw') or c.get('output') or None,
                            status=_map_status(numeric_status),
                            manufacturer=c.get('maker') or c.get('manufacturer'),
                            model=c.get('model') or c.get('modelNm'),
                            bid=c.get('bid'),
                            cpId=c.get('cpId'),
                            charger_code=c.get('csId'),
                            cs_cat_code=c.get('csCatCode'),
                            info_coll_date=c.get('infoCollDate'),
                            status_code=c.get('csStatCode'),
                            ch_start_date=c.get('chStartDate'),
                            last_ch_start_date=c.get('lastChStartDate'),
                            last_ch_end_date=c.get('lastChEndDate'),
                            updated_at=c.get('updateDate'),
                            raw=c
                        ))
        except Exception:
            # 충전기 상세 실패는 무시하고 기본 정보만 반환
            pass

        # parse lat/lon robustly: some provider payloads use 'x'/'y' while others use 'lat'/'lon' or 'latitude'/'longitude'
        raw_lat = item.get('y') or item.get('lat') or item.get('latitude') or item.get('latitudeValue')
        raw_lon = item.get('x') or item.get('lon') or item.get('longitude') or item.get('longitudeValue')
        try:
            lat_val = float(raw_lat) if raw_lat is not None else 0.0
        except Exception:
            lat_val = 0.0
        try:
            lon_val = float(raw_lon) if raw_lon is not None else 0.0
        except Exception:
            lon_val = 0.0

        # If coords are missing (0.0/0.0) and we have chargers, attempt to mark fallback
        coords_missing = (lat_val == 0.0 and lon_val == 0.0)
        extra_info = {k: v for k, v in item.items() if k not in ("csList", "id", "cpId", "cpName", "addr", "lat", "lon", "x", "y")}
        if coords_missing:
            extra_info.setdefault('notes', {})['coords_fallback'] = True

        # compute charger_count from chargers list
        charger_count_computed = len(chargers) if chargers is not None else 0
        # If coords missing, try to compute average coords from chargers' raw fields
        if coords_missing and chargers:
            lat_sum = 0.0
            lon_sum = 0.0
            count_coords = 0
            for c in chargers:
                raw = c.raw if hasattr(c, 'raw') and c.raw else c.get('raw') if isinstance(c, dict) else None
                if raw:
                    coords = _extract_coords_from_raw(raw)
                    if coords:
                        lat_sum += coords[0]
                        lon_sum += coords[1]
                        count_coords += 1
            if count_coords > 0:
                lat_val = lat_sum / count_coords
                lon_val = lon_sum / count_coords
                # unset coords_missing because we successfully filled them
                coords_missing = False
                extra_info.setdefault('notes', {})['coords_fallback_from_chargers'] = True

        # Build StationDetail using available station item and populated chargers.
        detail = StationDetail(
            id=station_id,
            name=item.get('cpName') or item.get('cp_name') or '',
            address=item.get('addr') or item.get('roadName') or item.get('address'),
            lat=lat_val,
            lon=lon_val,
            extra_info=extra_info,
            chargers=[c.dict() if hasattr(c, 'dict') else c for c in chargers]
        )

        # If mismatch was detected or coords are missing, but we have charger records,
        # prefer returning a charger-driven StationDetail so the client still gets charger specs.
        if (mismatch_detected or coords_missing) and chargers:
            # Build a minimal station detail from charger info (no reliable coords)
            fallback_detail = StationDetail(
                id=station_id,
                name=detail.name or f"Station {station_id}",
                address=detail.address,
                lat=detail.lat,
                lon=detail.lon,
                extra_info={**(detail.extra_info or {}), 'fallback_from_chargers': True},
                chargers=[c.dict() if hasattr(c, 'dict') else c for c in chargers]
            )
            try:
                await set_cache(cache_key, fallback_detail.dict())
            except Exception:
                logger.debug("Failed to set cache for fallback %s", cache_key)
            return fallback_detail

        # cache and return
        try:
            await set_cache(cache_key, detail.dict())
        except Exception:
            logger.debug("Failed to set cache for %s", cache_key)
        return detail

    async def get_raw_charger_payload(self, station_id: str) -> Dict[str, Any]:
        """Return raw station payload and charger payload from external API for debugging.

        Returns a dict: { "cp_key": str, "station_payload": <raw>, "charger_payload": <raw> }
        """
        # derive cp_key same as in get_station_detail
        if '_' in station_id:
            bid, cpId = station_id.split('_', 1)
        else:
            bid = ''
            cpId = station_id
        cp_key = f"P{bid}{cpId}"

        cond = {"cpKeyList": [cp_key], "searchStatus": False}
        station_payload = await self._post('/ws/chargePoint/curChargePoint', json=cond)
        charger_payload = await self._post('/ws/charger/curCharger', json={"cpKeyList": [cp_key]})

        return {"cp_key": cp_key, "station_payload": station_payload, "charger_payload": charger_payload}


station_service = StationService()
