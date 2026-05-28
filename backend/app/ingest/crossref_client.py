"""Crossref — DOI metadata fallback."""

import httpx

from app.logging import get_logger

log = get_logger(__name__)

CROSSREF = "https://api.crossref.org/works"


async def fetch_crossref(doi: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{CROSSREF}/{doi}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json().get("message")
    except Exception as e:
        log.warning("crossref.fetch_failed", doi=doi, error=str(e))
        return None
