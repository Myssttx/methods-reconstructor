"""FastAPI dependencies — auth, settings, rate limiting."""

from fastapi import Header, HTTPException

from app.config import get_settings


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    """C-4: Require X-API-Key header when API_KEY is configured.

    If API_KEY is empty, the endpoint is open (dev/demo mode).
    Set API_KEY in .env to lock down the API in production.
    """
    settings = get_settings()
    configured_key = settings.api_key
    if not configured_key:
        return  # No key configured — open access (dev mode)
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    if x_api_key != configured_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
