from typing import List, Dict, Any, Optional
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger("app.services.kepco_adapter")


class KepcoAdapter:
    """Adapter to call Kepco BigData EVchargeManage API and normalize results.

    This adapter calls the single endpoint and filters/paginates results in-code
    because the public API primarily accepts `addr` and returns a `data` list.
    """

    def __init__(self,
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 key_param_name: str = "apiKey",
                 return_type: str = "json",
                 timeout: int = 10):
        self.base_url = base_url or settings.EXTERNAL_STATION_API_BASE_URL
        self.api_key = api_key or settings.EXTERNAL_STATION_API_KEY
        self.key_param_name = key_param_name
        self.return_type = return_type
        self.timeout = timeout

    async def _fetch_all(self, addr: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.base_url:
            raise RuntimeError("Kepco base_url not configured")

        params = {}
        if self.api_key:
            params[self.key_param_name] = self.api_key
        if self.return_type:
            params["returnType"] = self.return_type
        if addr:
            params["addr"] = addr

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(self.base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            # Kepco returns {"data": [...]}
            if isinstance(data, dict):
                return data.get("data") or []
            if isinstance(data, list):
                return data
            return []

    @staticmethod
    def _within_bbox(item: Dict[str, Any], min_lat: float, max_lat: float, min_lng: float, max_lng: float) -> bool:
        try:
            lat = float(item.get("lat") or item.get("latitude") or 0)
            lng = float(item.get("longi") or item.get("lon") or item.get("longitude") or 0)
        except Exception:
            return False
        return (min_lat <= lat <= max_lat) and (min_lng <= lng <= max_lng)

    async def search(self, min_lat: float, max_lat: float, min_lng: float, max_lng: float,
                     page: int = 1, page_size: int = 20, addr: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return a page of items whose lat/lng fall within the bbox. If addr is
        provided it will be passed to the API to reduce result size.
        """
        items = await self._fetch_all(addr=addr)
        # Filter by bbox
        filtered = [it for it in items if self._within_bbox(it, min_lat, max_lat, min_lng, max_lng)]
        # paginate
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end]

    async def find_chargers(self, cp_ids: List[str]) -> List[Dict[str, Any]]:
        """Return charger records whose cpId (or csId/csId) matches any provided id.

        cp_ids: list of cpId strings (the API's cpId field) or csId values.
        """
        items = await self._fetch_all()
        out: List[Dict[str, Any]] = []
        cp_set = set([str(x) for x in cp_ids if x])
        for it in items:
            if str(it.get("cpId") or it.get("cpid") or it.get("cp_id") or "") in cp_set:
                out.append(it)
            elif str(it.get("csId") or it.get("csid") or "") in cp_set:
                out.append(it)
        return out

    async def get_station_by_csId(self, csId: str) -> Optional[Dict[str, Any]]:
        items = await self._fetch_all()
        for it in items:
            if str(it.get("csId")) == str(csId):
                return it
        return None
