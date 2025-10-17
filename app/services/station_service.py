from typing import List, Optional, Dict, Any
import asyncio
import math
import httpx
from app.core.config import settings
from app.redis_client import get_cache, set_cache
from app.schemas.station import StationSummary, StationDetail, ChargerDetail


class ExternalAPIError(Exception):
    pass


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

        # 외부 사이트(실제 chargeinfo 페이지)의 JS를 분석한 결과, 검색은
        # POST /ws/chargePoint/curChargePoint (또는 searchChargePoint)로
        # cond JSON 객체를 전송하는 방식입니다. 여기서는 단순히 지도 중심
        # + radius를 이용해 bounding box를 계산하여 cond를 구성합니다.

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
        payload = await self._post('/ws/chargePoint/curChargePoint', json=cond)

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

        await set_cache(cache_key, [s.dict() for s in summaries])
        return summaries

    async def get_station_detail(self, station_id: str) -> StationDetail:
        cache_key = f"station:detail:{station_id}"
        cached = await get_cache(cache_key)
        if cached:
            return StationDetail(**cached)

        # station_id expected format: "{bid}_{cpId}" as returned by search_stations
        if '_' in station_id:
            bid, cpId = station_id.split('_', 1)
        else:
            # fallback: try to call external endpoint directly with provided id
            bid = ''
            cpId = station_id

        cp_key = f"P{bid}{cpId}"

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

        # charger 상세 조회
        chargers: List[ChargerDetail] = []
        try:
            ch_resp = await self._post('/ws/charger/curCharger', json={"cpKeyList": [cp_key]})
            if isinstance(ch_resp, list):
                for c in ch_resp:
                    chargers.append(ChargerDetail(
                        id=str(c.get('chargerId') or c.get('id') or c.get('csId') or c.get('csId') ),
                        station_id=station_id,
                        connector_types=[c.get('connectorType') or c.get('connector') or ''],
                        max_power_kw=c.get('outputKw') or c.get('output') or None,
                        status=c.get('csStatCode') or c.get('status'),
                        manufacturer=c.get('maker') or c.get('manufacturer'),
                        model=c.get('model') or c.get('modelNm')
                    ))
        except Exception:
            # 충전기 상세 실패는 무시하고 기본 정보만 반환
            pass

        detail = StationDetail(
            id=station_id,
            name=item.get('cpName') or item.get('cp_name') or '',
            address=item.get('addr') or item.get('roadName') or item.get('address'),
            lat=float(item.get('lat') or item.get('latitude') or 0.0),
            lon=float(item.get('lon') or item.get('longitude') or 0.0),
            extra_info={k: v for k, v in item.items() if k not in ("csList", "id", "cpId", "cpName", "addr", "lat", "lon")},
            chargers=chargers
        )

        await set_cache(cache_key, detail.dict())
        return detail


station_service = StationService()
