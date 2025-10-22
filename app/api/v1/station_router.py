"""FastAPI router for Station and Charger endpoints"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_session
from app.api.deps import frontend_api_key_required
from app.services.station_service import StationService
from app.schemas.station import StationSummary, StationDetail, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stations", tags=["Stations"])


@router.get(
    "",
    response_model=List[StationSummary],
    summary="Search charging stations by location",
    description="""
    Search for EV charging stations within a specified radius of given coordinates.
    
    The system uses a 3-tier data retrieval strategy:
    1. Redis cache (fastest)
    2. Database (static data)
    3. KEPCO API (fresh data)
    
    Radius is automatically adjusted to nearest threshold: 500, 1000, 3000, 5000, or 10000 meters.
    """
)
async def search_stations(
    lat: float = Query(..., description="User latitude", ge=-90, le=90),
    lon: float = Query(..., description="User longitude", ge=-180, le=180), 
    radius: int = Query(1000, description="Search radius in meters", ge=100, le=10000),
    db: AsyncSession = Depends(get_async_session),
    _: bool = Depends(frontend_api_key_required)
):
    """Search charging stations by location"""
    try:
        service = StationService(db)
        stations = await service.search_stations_by_location(lat, lon, radius)
        
        # Convert to response model
        response = []
        for station in stations:
            response.append(StationSummary(**station))
        
        logger.info(f"Returned {len(response)} stations for location ({lat}, {lon}) radius {radius}m")
        return response
        
    except Exception as e:
        logger.error(f"Error searching stations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search stations")


@router.get(
    "/{cs_id}/chargers",
    response_model=StationDetail,
    summary="Get charger details for a station",
    description="""
    Get detailed information about all chargers at a specific charging station.
    
    Returns station name, available charging methods, and detailed specs for each charger
    including real-time status (refreshed every 30 minutes from KEPCO API).
    """
)
async def get_station_chargers(
    cs_id: str,
    addr: str = Query(..., description="Station address (required for API fallback)"),
    db: AsyncSession = Depends(get_async_session),
    _: bool = Depends(frontend_api_key_required)
):
    """Get charger details for a station"""
    try:
        service = StationService(db)
        station_detail = await service.get_station_chargers(cs_id, addr)
        
        if not station_detail:
            raise HTTPException(status_code=404, detail=f"Station {cs_id} not found")
        
        logger.info(f"Returned charger details for station {cs_id}")
        return StationDetail(**station_detail)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting station chargers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get station chargers")


@router.get(
    "/{cs_id}",
    response_model=StationDetail,
    summary="Get station details (alias for /chargers)",
    description="Alias endpoint for getting station charger details"
)
async def get_station_detail(
    cs_id: str,
    addr: str = Query(..., description="Station address"),
    db: AsyncSession = Depends(get_async_session),
    _: bool = Depends(frontend_api_key_required)
):
    """Get station details (alias for chargers endpoint)"""
    return await get_station_chargers(cs_id, addr, db, _)