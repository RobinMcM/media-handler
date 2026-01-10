import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-Internal-API-Key", auto_error=False)


def get_api_keys():
    keys_env = os.getenv("INTERNAL_API_KEYS", "")
    if not keys_env:
        raise RuntimeError("INTERNAL_API_KEYS environment variable not set")
    return [key.strip() for key in keys_env.split(",")]


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    
    valid_keys = get_api_keys()
    if api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return api_key
