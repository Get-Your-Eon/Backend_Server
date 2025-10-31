"""Simple Station Router - Independent from subsidy functionality"""

from fastapi import APIRouter, Query, Depends, HTTPException
from typing import List
import logging
from app.api.deps import frontend_api_key_required

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stations", tags=["Station"], summary="Search charging stations by location")
async def search_stations(
    lat: float = Query(..., description="Latitude (required)", ge=-90, le=90),
    lon: float = Query(..., description="Longitude (required)", ge=-180, le=180), 
    radius: int = Query(..., description="Search radius in meters (required) - 5000,10000,15000", ge=100, le=15000),
    page: int = Query(1, description="Page number", ge=1),
    limit: int = Query(20, description="Results per page", ge=1, le=100),
    _: bool = Depends(frontend_api_key_required)
):
    """
    Search for EV charging stations within specified radius.
    
    Required parameters:
    - lat: Latitude coordinate  
    - lon: Longitude coordinate
    - radius: Search radius in meters
    - x-api-key: API key in header
    
    Optional parameters:
    - page: Page number (default: 1)
    - limit: Results per page (default: 20)
    """
    try:
        # For now, return a simple message indicating the endpoint is ready
        # This ensures no interference with subsidy functionality
        # Updated: Force new deployment
        return {
            "message": "Station search endpoint is ready (v2)",
            "status": "active",
            "timestamp": "2025-10-23",
            "parameters": {
                "lat": lat,
                "lon": lon, 
                "radius": radius,
                "page": page,
                "limit": limit
            },
            "note": "Station functionality is isolated from subsidy features"
        }
    except Exception as e:
        logger.error(f"Error in station search: {e}")
        raise HTTPException(status_code=500, detail="Station search temporarily unavailable")


@router.get("/stations/{station_id}", tags=["Station"], summary="Get station details")
async def get_station_detail(
    station_id: str,
    _: bool = Depends(frontend_api_key_required)
):
    """Get detailed information about a specific charging station"""
    return {
        "message": "Station detail endpoint is ready", 
        "station_id": station_id,
        "note": "Station functionality is isolated from subsidy features"
    }


@router.get("/stations/{station_id}/chargers", tags=["Station"], summary="Get chargers for station")
async def get_station_chargers(
    station_id: str,
    _: bool = Depends(frontend_api_key_required)
):
    """Get charger information for a specific station"""
    return {
        "message": "Station chargers endpoint is ready",
        "station_id": station_id, 
        "note": "Station functionality is isolated from subsidy features"
    }