from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session
from app.api.deps import frontend_api_key_required

router = APIRouter()


@router.get("/inspect/station/{station_id}")
async def inspect_station_db(station_id: str, db: AsyncSession = Depends(get_async_session), _ok: bool = Depends(frontend_api_key_required)):
    """Return stored station location text for given station id (read-only).

    Returns: { "id": str, "location_text": str | null }
    """
    try:
        # Allow lookup by station_code (string external id) or by numeric PK (id::text)
        q = text(
            "SELECT id, station_code, ST_AsText(location) as location_text "
            "FROM stations "
            "WHERE station_code = :id OR id::text = :id "
            "LIMIT 1"
        )
        result = await db.execute(q, {"id": station_id})
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="station not found")
        m = row._mapping
        return {"id": m.get("id"), "station_code": m.get("station_code"), "location_text": m.get("location_text")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
