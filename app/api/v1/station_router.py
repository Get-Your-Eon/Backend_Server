from fastapi import APIRouter, Query, Path, Depends, HTTPException
from typing import List, Union
import logging
from app.services.station_service import station_service, ExternalAPIError
from fastapi.responses import JSONResponse
from app.schemas.station import StationSummary, StationDetail, ChargerDetail
from app.api.deps import frontend_api_key_required


def _parse_coord(value: Union[str, float], name: str) -> float:
    """안전하게 문자열로 온 좌표를 float로 변환합니다. 실패 시 HTTP 400 반환."""
    try:
        if isinstance(value, str):
            # 허용되는 구분자나 공백 제거
            v = value.strip()
            return float(v)
        return float(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {name} coordinate: {value}")

router = APIRouter()


@router.get("/stations", response_model=List[StationSummary], tags=["Station"])
async def search_stations(lat: Union[str, float] = Query(...), lon: Union[str, float] = Query(...), radius_m: int = Query(1000, alias="radius"), page: int = 1, limit: int = 20, _ok: bool = Depends(frontend_api_key_required)):
    # 프론트엔드에서 lat/lon이 문자열로 올 수 있으므로 안전하게 파싱
    lat_f = _parse_coord(lat, "lat")
    lon_f = _parse_coord(lon, "lon")
    try:
        return await station_service.search_stations(lat=lat_f, lon=lon_f, radius_m=radius_m, page=page, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/stations/{station_id}", response_model=StationDetail, tags=["Station"])
async def get_station(station_id: str = Path(...), _ok: bool = Depends(frontend_api_key_required)):
    logger = logging.getLogger("app.api.v1.station_router")
    try:
        result = await station_service.get_station_detail(station_id)
        if result is None:
            logger.info("station_service.get_station_detail returned None for %s", station_id)
            raise HTTPException(status_code=404, detail="Station not found")
        return result
    except ExternalAPIError as e:
        # External API explicitly did not find the station or returned a known error
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        # Re-raise FastAPI HTTPExceptions untouched
        raise
    except Exception:
        # Log full traceback and return a 502 to the client to avoid leaking internals
        logger.exception("Unhandled error in get_station for %s", station_id)
        raise HTTPException(status_code=502, detail="Internal upstream error")


@router.get("/stations/{station_id}/debug_raw", tags=["Station"], summary="(debug) raw resolved station detail without response_model validation")
async def get_station_debug_raw(station_id: str = Path(...), _ok: bool = Depends(frontend_api_key_required)):
    """Debug endpoint: return the raw dict produced by station_service.get_station_detail() without FastAPI response_model validation.

    This endpoint should only be used for debugging and returns internal data shapes. It is protected by the same x-api-key dependency.
    """
    logger = logging.getLogger("app.api.v1.station_router.debug")
    try:
        result = await station_service.get_station_detail(station_id)
    except ExternalAPIError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled error in debug_raw for %s", station_id)
        raise HTTPException(status_code=502, detail="Internal upstream error")

    if result is None:
        raise HTTPException(status_code=404, detail="Station not found")

    # Return raw dict to avoid FastAPI model validation issues when debugging
    try:
        return JSONResponse(content=result.dict())
    except Exception:
        # If conversion to dict fails, attempt shallow manual serialization
        try:
            content = {
                'id': getattr(result, 'id', None),
                'name': getattr(result, 'name', None),
                'lat': getattr(result, 'lat', None),
                'lon': getattr(result, 'lon', None),
                'extra_info': getattr(result, 'extra_info', None),
                'chargers': [c.dict() if hasattr(c, 'dict') else c for c in (getattr(result, 'chargers', []) or [])]
            }
            return JSONResponse(content=content)
        except Exception:
            logger.exception("Failed to serialize station detail for %s", station_id)
            raise HTTPException(status_code=500, detail="Failed to serialize station detail")
    except ExternalAPIError as e:
        # External API explicitly did not find the station or returned a known error
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        # Re-raise FastAPI HTTPExceptions untouched
        raise
    except Exception as e:
        # Log full traceback and return a 502 to the client to avoid leaking internals
        logger.exception("Unhandled error in get_station for %s", station_id)
        raise HTTPException(status_code=502, detail="Internal upstream error")


@router.get("/stations/{station_id}/chargers", response_model=List[ChargerDetail], tags=["Charger"])
async def station_chargers(station_id: str = Path(...), _ok: bool = Depends(frontend_api_key_required)):
    """Return list of chargers for a station."""
    try:
        detail = await station_service.get_station_detail(station_id)
        return detail.chargers or []
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/stations/{station_id}/chargers/raw", tags=["Charger"], summary="(debug) raw station and charger payloads")
async def station_chargers_raw(station_id: str = Path(...), _ok: bool = Depends(frontend_api_key_required)):
    """Return the raw payloads returned by the external APIs for given station cpKey.

    WARNING: Debug endpoint; do not expose in production without access control.
    """
    try:
        raw = await station_service.get_raw_charger_payload(station_id)
        return raw
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/stations/{station_id}/chargers/{charger_id}", response_model=ChargerDetail, tags=["Charger"])
async def station_charger_detail(station_id: str = Path(...), charger_id: str = Path(...), _ok: bool = Depends(frontend_api_key_required)):
    """Return a single charger spec for given station and charger id."""
    try:
        detail = await station_service.get_station_detail(station_id)
        for c in (detail.chargers or []):
            if c.id == charger_id or (hasattr(c, 'charger_code') and getattr(c, 'charger_code') == charger_id):
                return c
        raise HTTPException(status_code=404, detail="Charger not found for station")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/chargers/{charger_id}", response_model=ChargerDetail, tags=["Charger"])
async def get_charger(charger_id: str = Path(...), _ok: bool = Depends(frontend_api_key_required)):
    # Currently delegate to station detail lookup — could be improved to call dedicated endpoint
    try:
        # naive approach: attempt to parse station id from charger id or call external endpoint
        detail = await station_service.get_station_detail(charger_id)
        # try to find charger
        for c in detail.chargers or []:
            if c.id == charger_id:
                return c
        raise HTTPException(status_code=404, detail="Charger not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

