from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings
from app.redis_client import get_redis_client

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


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
