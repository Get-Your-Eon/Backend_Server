from fastapi import APIRouter, Header, HTTPException, status, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings
from app.redis_client import get_redis_client
from app.api.deps import frontend_api_key_required

router = APIRouter(prefix="/admin", tags=["admin"])


class CacheKeyRequest(BaseModel):
    key: str


@router.post("/cache")
async def delete_cache_key(req: CacheKeyRequest, x_admin_key: Optional[str] = Header(None)):
    """Delete a single redis cache key. Protected by ADMIN_API_KEY env var.

    Request body: { "key": "station:detail:PCGCGH00140" }
    Header: x-admin-key: <ADMIN_API_KEY>
    """
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin API not configured")
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")

    redis_client = await get_redis_client()
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis not available")
    try:
        deleted = await redis_client.delete(req.key)
        return {"deleted": bool(deleted), "key": req.key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache-unlocked")
async def delete_cache_key_frontend(req: CacheKeyRequest, _ok: bool = Depends(frontend_api_key_required)):
    """Temporary endpoint: allow frontend API key holders to delete station detail cache keys.

    This endpoint intentionally restricts key deletion to keys that start with 'station:detail:' to limit scope.
    Use this only when Render shell access or ADMIN_API_KEY is not available.
    """
    # restrict to station detail keys only
    if not req.key or not req.key.startswith("station:detail:"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only station detail keys are allowed")

    redis_client = await get_redis_client()
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis not available")
    try:
        deleted = await redis_client.delete(req.key)
        return {"deleted": bool(deleted), "key": req.key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inspect-db/station/{station_id}")
async def inspect_station_db_admin(station_id: str, db: AsyncSession = Depends(get_async_session), _ok: bool = Depends(frontend_api_key_required)):
    """Read-only: return ST_AsText(location) for given station id from DB.

    Restricted to frontend API keys to avoid exposing admin credentials.
    """
    try:
        q = text("SELECT id, ST_AsText(location) as location_text FROM stations WHERE id = :id LIMIT 1")
        result = await db.execute(q, {"id": station_id})
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="station not found")
        m = row._mapping
        return {"id": m.get("id"), "location_text": m.get("location_text")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
