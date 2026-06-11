from __future__ import annotations
"""OpenAlex — paper metadata + reference graph."""

import re

import httpx

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)

OPENALEX = "https://api.openalex.org"


def parse_doi(s: str) -> str | None:
    s = s.strip()
    if s.lower().startswith("doi:"):
        s = s[4:]
    m = re.search(r"10\.\d{4,9}/[^\s?#]+", s, re.IGNORECASE)
    if not m:
        return None
    return m.group(0).rstrip(".,;:)]}").lower()


async def fetch_openalex_by_doi(doi: str) -> dict | None:
    settings = get_settings()
    params = {}
    if settings.openalex_email:
        params["mailto"] = settings.openalex_email
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{OPENALEX}/works/doi:{doi}", params=params)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        log.warning("openalex.fetch_failed", doi=doi, error=str(e))
        return None
