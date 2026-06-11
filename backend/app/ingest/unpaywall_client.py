from __future__ import annotations
"""Unpaywall — find an open-access PDF for a paywalled DOI."""

import httpx

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)

UNPAYWALL = "https://api.unpaywall.org/v2"


async def find_oa_url(doi: str) -> str | None:
    settings = get_settings()
    if not settings.unpaywall_email:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{UNPAYWALL}/{doi}",
                params={"email": settings.unpaywall_email},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            best = data.get("best_oa_location")
            if best and best.get("url_for_pdf"):
                return best["url_for_pdf"]
            if best and best.get("url"):
                return best["url"]
    except Exception as e:
        log.warning("unpaywall.fetch_failed", doi=doi, error=str(e))
    return None
