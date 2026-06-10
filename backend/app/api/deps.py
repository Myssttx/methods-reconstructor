"""FastAPI dependencies — auth, settings, rate limiting."""

from fastapi import Header, HTTPException, Query

from app.config import get_settings


async def require_api_key(
    x_api_key: str = Header(default=""),
    api_key: str = Query(default=""),  # fallback for direct browser navigations (exports)
) -> None:
    """C-4: Require X-API-Key header (or ?api_key= param) when API_KEY is configured.

    If API_KEY is empty, the endpoint is open (dev/demo mode).
    Set API_KEY in .env to lock down the API in production.
    """
    settings = get_settings()
    configured_key = settings.api_key
    if not configured_key:
        return  # No key configured — open access (dev mode)
    provided = x_api_key or api_key
    if not provided:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    if provided != configured_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
