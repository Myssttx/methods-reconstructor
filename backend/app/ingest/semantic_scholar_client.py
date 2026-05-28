"""Semantic Scholar — fallback metadata + reference graph."""

import httpx

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)

S2 = "https://api.semanticscholar.org/graph/v1"


async def fetch_s2_paper(doi: str) -> dict | None:
    settings = get_settings()
    headers = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
    try:
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            resp = await client.get(
                f"{S2}/paper/DOI:{doi}",
                params={"fields": "title,authors,year,venue,abstract,references"},
            )
            if resp.status_code != 200:
                return None
            return resp.json()
    except Exception as e:
        log.warning("s2.fetch_failed", doi=doi, error=str(e))
        return None
