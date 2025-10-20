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
from app.services.kepco_adapter import KepcoAdapter
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


def _extract_station_info_from_charger_raw(raw: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Try to extract station-level name/address hints from a charger raw payload."""
    if not raw or not isinstance(raw, dict):
        return {"name": None, "address": None}
    name = raw.get('cpName') or raw.get('cp_name') or raw.get('station_name') or raw.get('cpNm') or raw.get('chargerSiteName')
    # address can be under several keys depending on provider
    address = raw.get('addr') or raw.get('address') or raw.get('roadName') or raw.get('siteAddr')
    try:
        name = str(name).strip() if name is not None else None
    except Exception:
        name = None
    try:
        address = str(address).strip() if address is not None else None
    except Exception:
        address = None
    return {"name": name or None, "address": address or None}


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
        # Kepco adapter initialized with environment-driven params
        self.kepco = KepcoAdapter(
            base_url=self.base_url,
            api_key=self.api_key,
            key_param_name=getattr(settings, 'EXTERNAL_STATION_API_KEY_PARAM_NAME', 'apiKey'),
            return_type=getattr(settings, 'EXTERNAL_STATION_API_RETURN_TYPE', 'json'),
            timeout=getattr(settings, 'EXTERNAL_STATION_API_TIMEOUT_SEED_SECONDS', 30)
        )

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key and self.auth_type == "header":
            headers[self.header_name] = self.api_key
        return headers

    def _build_params(self) -> Dict[str, str]:
        params: Dict[str, str] = {}
        if self.api_key and self.auth_type == "query":
            # allow configurable parameter name (e.g., Kepco uses 'apiKey')
            key_name = getattr(settings, 'EXTERNAL_STATION_API_KEY_PARAM_NAME', 'apiKey')
            params[key_name] = self.api_key
        # allow forcing return type via env (json/xml)
        try:
            return_type = getattr(settings, 'EXTERNAL_STATION_API_RETURN_TYPE', None)
            if return_type:
                params['returnType'] = return_type
        except Exception:
            pass
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

    # Use Kepco adapter to search for items within bounding box.
    # Kepco returns flat charger records in `data`; group by csId/cpId for stations.
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

        # Kepco adapter returns charger-level records; filter by bbox
        items = await self.kepco.search(minLat, maxLat, minLng, maxLng, page=page, page_size=limit)

        summaries: List[StationSummary] = []
        cp_key_list: List[str] = []
        # Kepco fields mapping: cpId, csId, cpNm, csNm, addr, lat, longi, cpStat, cpTp, statUpdateDatetime
        # Group by station (csId) to compute station-level summary
        stations_by_cs: Dict[str, Dict[str, Any]] = {}
        for it in items:
            csId = str(it.get('csId') or it.get('csid') or it.get('csId') or '')
            cpId = str(it.get('cpId') or it.get('cpid') or '')
            lat_val = it.get('lat') or it.get('latitude') or None
            lon_val = it.get('longi') or it.get('longi') or it.get('longitude') or None
            if csId not in stations_by_cs:
                stations_by_cs[csId] = {
                    'csId': csId,
                    'csNm': it.get('csNm') or it.get('cs_name') or None,
                    'addr': it.get('addr') or None,
                    'lat': float(lat_val) if lat_val not in (None, '') else 0.0,
                    'lon': float(lon_val) if lon_val not in (None, '') else 0.0,
                    'chargers': set()
                }
            stations_by_cs[csId]['chargers'].add(cpId or (it.get('cpNm') or ''))

        for cs, info in stations_by_cs.items():
            summaries.append(StationSummary(
                id=str(info.get('csId')),
                name=info.get('csNm') or f"Station {info.get('csId')}",
                address=info.get('addr'),
                lat=float(info.get('lat') or 0.0),
                lon=float(info.get('lon') or 0.0),
                distance_m=None,
                charger_count=len(info.get('chargers') or [])
            ))

        # 충전기 상세를 얻어 각 충전소의 충전기 수를 채웁니다.
        # No additional charger lookup is necessary as Kepco returns charger-level rows

        # persist results to DB (best-effort)
        # Persist station summaries as best-effort (DB expects stations+chargers)
        try:
            async with AsyncSessionLocal() as session:
                # Convert to minimal upsert shape: for each station, include empty chargers list
                await upsert_stations_and_chargers(session, [{
                    'id': s.id,
                    'name': s.name,
                    'address': s.address,
                    'lat': s.lat,
                    'lon': s.lon,
                    'chargers': []
                } for s in summaries])
        except Exception:
            logger.exception("Failed to upsert stations from Kepco search")

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

        # For Kepco API, station and charger rows are returned in the same data set.
        # We query items with matching csId (station id) or cpId (charger id) and
        # aggregate chargers under their csId.
        # Attempt to find station rows by csId (station id). If the input is of form
        # '{csId}' we directly use it; if it's a cpKey-like id, try to extract csId.
        cs_id = station_id
        if station_id.startswith('P'):
            # Attempt to parse P{bid}{cpId} -> we don't have csId directly; fallback to full scan
            cs_id = None
        elif '_' in station_id:
            # legacy '{bid}_{cpId}' form — can't reliably map to csId; fallback to searching by cpId
            cs_id = None

        # Fetch all items (or filtered by addr) and locate relevant rows
        items = []
        try:
            items = await self.kepco._fetch_all()
        except Exception:
            raise ExternalAPIError('Failed to fetch data from Kepco API')

        # find station-level item(s)
        station_items = []
        charger_items = []
        for it in items:
            # normalize keys
            this_cs = str(it.get('csId') or it.get('csid') or '')
            this_cp = str(it.get('cpId') or it.get('cpid') or '')
            if cs_id and this_cs and cs_id == this_cs:
                station_items.append(it)
            if '_' in station_id:
                # if input is bid_cpId, match cpId
                _, requested_cp = station_id.split('_', 1)
                if this_cp == requested_cp:
                    charger_items.append(it)
            # if input equals cpId
            if station_id == this_cp:
                charger_items.append(it)

        # If no explicit station_items found, but charger_items exist, derive station info from chargers
        # mismatch_detected indicates we had to fall back to charger-level records
        mismatch_detected = False
        item = None
        if station_items:
            item = station_items[0]
        elif charger_items:
            # We couldn't find a station-level row; we'll derive station info from charger rows
            mismatch_detected = True
            item = charger_items[0]
        else:
            raise ExternalAPIError('Station not found from Kepco API')

        # charger 상세 조회
        # Build chargers list from items where csId matches or cpId matches
        chargers = []
        for it in items:
            this_cs = str(it.get('csId') or it.get('csid') or '')
            this_cp = str(it.get('cpId') or it.get('cpid') or '')
            if (station_id and ('_' in station_id and this_cp == station_id.split('_',1)[1])) or (cs_id and this_cs == cs_id) or (station_id == this_cp):
                connector_types = []
                cpTp = it.get('cpTp')
                if cpTp is not None:
                    # map Kepco cpTp numeric codes to textual connector types
                    try:
                        ctp = int(cpTp)
                        if ctp == 1:
                            connector_types = ['B-type(5pin)']
                        elif ctp == 2:
                            connector_types = ['C-type(5pin)']
                        elif ctp == 5:
                            connector_types = ['CHAdeMO']
                        elif ctp == 6:
                            connector_types = ['AC3']
                        elif ctp in (7,8):
                            connector_types = ['DC Combo']
                        else:
                            connector_types = [str(cpTp)]
                    except Exception:
                        connector_types = [str(cpTp)]

                status_code = it.get('cpStat')
                # Kepco cpStat mapping: 1:충전가능 2:충전중 3:고장/점검 4:통신장애 5:통신미연결
                status = None
                try:
                    sc = int(status_code)
                    if sc == 1:
                        status = 'AVAILABLE'
                    elif sc == 2:
                        status = 'CHARGING'
                    elif sc == 3:
                        status = 'OUT_OF_ORDER'
                    elif sc == 4:
                        status = 'COMMUNICATION_ERROR'
                    elif sc == 5:
                        status = 'NOT_CONNECTED'
                    else:
                        status = f'UNKNOWN_{sc}'
                except Exception:
                    status = str(status_code)

                chargers.append(ChargerDetail(
                    id=str(it.get('cpId') or it.get('cpid') or it.get('cpId')),
                    station_id=str(it.get('csId') or it.get('csid') or ''),
                    connector_types=connector_types,
                    max_power_kw=None,
                    status=status,
                    manufacturer=None,
                    model=None,
                    bid=None,
                    cpId=str(it.get('cpId') or it.get('cpid') or ''),
                    charger_code=str(it.get('cpId') or it.get('cpid') or ''),
                    cs_cat_code=None,
                    info_coll_date=None,
                    status_code=status_code,
                    ch_start_date=None,
                    last_ch_start_date=None,
                    last_ch_end_date=None,
                    updated_at=it.get('statUpdateDatetime'),
                    raw=it
                ))

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
                # raw payload may be stored either on the pydantic object or dict form
                raw = None
                if hasattr(c, 'raw') and getattr(c, 'raw'):
                    raw = getattr(c, 'raw')
                elif isinstance(c, dict):
                    raw = c.get('raw')
                # try extracting coords from known keys first
                if raw:
                    coords = _extract_coords_from_raw(raw)
                    if coords:
                        lat_sum += coords[0]
                        lon_sum += coords[1]
                        count_coords += 1
                        continue
                # As a fallback, try parsing common string fields on the charger record
                # Some providers embed lat/lon on top-level charger fields like 'lat'/'lon' or 'y'/'x'
                if isinstance(c, dict):
                    maybe_lat = c.get('lat') or c.get('y') or c.get('latitude')
                    maybe_lon = c.get('lon') or c.get('x') or c.get('longitude')
                    try:
                        if maybe_lat is not None and maybe_lon is not None:
                            lat_f = float(maybe_lat)
                            lon_f = float(maybe_lon)
                            # ignore zero coords
                            if lat_f != 0.0 or lon_f != 0.0:
                                lat_sum += lat_f
                                lon_sum += lon_f
                                count_coords += 1
                    except Exception:
                        pass
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
            chargers=[c.dict() if hasattr(c, 'dict') else c for c in chargers],
            charger_count=charger_count_computed
        )

        # If mismatch was detected or coords are missing, but we have charger records,
        # prefer returning a charger-driven StationDetail constructed only from chargers
        # that match the requested cp_key / station_id. This avoids mixing station info
        # from an unrelated fallback station returned by the provider.
        if (mismatch_detected or coords_missing) and chargers:
            # Filter chargers to those that match the requested cp_key (by bid+cpId)
            def charger_matches_requested(c: Any) -> bool:
                try:
                    raw = c.raw if hasattr(c, 'raw') else (c if isinstance(c, dict) else None)
                    bid = (raw.get('bid') if raw and 'bid' in raw else (getattr(c, 'bid', None))) or ''
                    cpId = (raw.get('cpId') or raw.get('cpid') if raw and ('cpId' in raw or 'cpid' in raw) else (getattr(c, 'cpId', None) or getattr(c, 'cpid', None))) or ''
                    key = f"{bid}_{cpId}"
                    # requested id in responses uses '{bid}_{cpId}' or station_id may be different formats
                    if '_' in station_id:
                        return key == station_id
                    # if station_id is a 'P...' cp_key or similar, compare by cp_key suffix
                    if station_id.startswith('P'):
                        return (f"P{bid}{cpId}") == station_id
                    return True
                except Exception:
                    return False

            matching_chargers = [c for c in chargers if charger_matches_requested(c)]
            if matching_chargers:
                # derive station name/address from chargers if station item seems wrong
                derived_name = None
                derived_address = None
                lat_sum = 0.0
                lon_sum = 0.0
                coord_count = 0
                for c in matching_chargers:
                    raw = c.raw if hasattr(c, 'raw') else (c if isinstance(c, dict) else None)
                    if raw:
                        info = _extract_station_info_from_charger_raw(raw)
                        if not derived_name and info.get('name'):
                            derived_name = info.get('name')
                        if not derived_address and info.get('address'):
                            derived_address = info.get('address')
                        coords = _extract_coords_from_raw(raw)
                        if coords:
                            lat_sum += coords[0]
                            lon_sum += coords[1]
                            coord_count += 1
                    # also check top-level fields on the ChargerDetail if provided as dict
                    if isinstance(c, dict):
                        maybe_name = c.get('cpName') or c.get('cp_name')
                        maybe_addr = c.get('addr') or c.get('address')
                        if not derived_name and maybe_name:
                            derived_name = maybe_name
                        if not derived_address and maybe_addr:
                            derived_address = maybe_addr

                if coord_count > 0:
                    derived_lat = lat_sum / coord_count
                    derived_lon = lon_sum / coord_count
                else:
                    # Do NOT reuse 'detail' coords when the station item is unrelated.
                    derived_lat = 0.0
                    derived_lon = 0.0

                # Avoid returning an unrelated station name/address coming from the
                # original 'item' (which may be a provider fallback). Only use
                # derived_name/derived_address when they are present on chargers.
                # Otherwise provide a neutral placeholder to avoid leaking wrong info.
                safe_name = derived_name or f"Station {station_id}"
                safe_address = derived_address or None

                fallback_detail = StationDetail(
                    id=station_id,
                    name=safe_name,
                    address=safe_address,
                    lat=derived_lat,
                    lon=derived_lon,
                    extra_info={**(detail.extra_info or {}), 'fallback_from_chargers': True, 'suppressed_unrelated_station_name': True},
                    chargers=[c.dict() if hasattr(c, 'dict') else c for c in matching_chargers],
                    charger_count=len(matching_chargers)
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
