from fastapi import Header, HTTPException
from typing import List
import os


def get_frontend_api_keys() -> List[str]:
    raw = os.getenv("FRONTEND_API_KEYS", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def frontend_api_key_required(x_api_key: str = Header(...)) -> bool:
    keys = get_frontend_api_keys()
    if not keys:
        # no keys configured -> deny
        raise HTTPException(status_code=403, detail="API keys not configured")
    if x_api_key not in keys:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True
