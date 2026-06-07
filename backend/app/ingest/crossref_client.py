"""Crossref — DOI metadata fallback."""

import re

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


async def resolve_citation(citation: str) -> str | None:
    """Resolve a raw bibliography entry to a DOI using Crossref ranking."""
    if not citation.strip():
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                CROSSREF,
                params={
                    "query.bibliographic": citation,
                    "rows": 3,
                    "select": "DOI,title,author,published",
                },
            )
            resp.raise_for_status()
            items = resp.json().get("message", {}).get("items", [])
            if not items:
                return None
            top = items[0]
            titles = top.get("title") or []
            candidate_title = titles[0] if titles else ""
            if candidate_title and not _citation_contains_title(citation, candidate_title):
                log.info("crossref.resolve_rejected", title=candidate_title)
                return None
            doi = top.get("DOI")
            return doi.lower() if doi else None
    except Exception as e:
        log.warning("crossref.resolve_failed", error=str(e))
        return None


def _citation_contains_title(citation: str, title: str) -> bool:
    title_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", title.casefold())
        if len(token) >= 4
    }
    if not title_tokens:
        return False
    citation_tokens = set(re.findall(r"[a-z0-9]+", citation.casefold()))
    return len(title_tokens & citation_tokens) / len(title_tokens) >= 0.6
