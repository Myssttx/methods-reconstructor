"""Crossref — DOI metadata fallback."""

import asyncio
import re

import httpx

from app.logging import get_logger

log = get_logger(__name__)

CROSSREF = "https://api.crossref.org/works"
# Module-level shared client (M-11: reuse TCP connections across calls).
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def fetch_crossref(doi: str) -> dict | None:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = _get_client()
            resp = await client.get(f"{CROSSREF}/{doi}")
            if resp.status_code == 429 and attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json().get("message")
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            log.warning("crossref.fetch_failed", doi=doi, error=str(e))
            return None
    return None


async def resolve_citation(citation: str) -> str | None:
    """Resolve a raw bibliography entry to a DOI using Crossref ranking."""
    if not citation.strip():
        return None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = _get_client()
            resp = await client.get(
                CROSSREF,
                params={
                    "query.bibliographic": citation,
                    "rows": 3,
                    "select": "DOI,title,author,published",
                },
            )
            if resp.status_code == 429 and attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
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
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            log.warning("crossref.resolve_failed", error=str(e))
            return None
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
    # M-10: tightened from 0.6 to 0.75 to reduce wrong-DOI returns.
    return len(title_tokens & citation_tokens) / len(title_tokens) >= 0.75
