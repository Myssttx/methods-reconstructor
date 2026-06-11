from __future__ import annotations
"""arXiv: abstract + PDF URL. Primary working ingest path."""

import re
from datetime import timezone, datetime

import arxiv

from app.logging import get_logger
from app.models import Author, Paper, PaperSource, Section

log = get_logger(__name__)

ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")


def parse_arxiv_id(s: str) -> str | None:
    """Accept `arxiv:2301.12345`, full URLs, or bare ids."""
    s = s.strip()
    if s.startswith("arxiv:"):
        s = s[len("arxiv:") :]
    m = ARXIV_ID_RE.search(s)
    return m.group(1) if m else None


def fetch_arxiv(arxiv_id: str) -> Paper | None:
    try:
        search = arxiv.Search(id_list=[arxiv_id])
        results = list(search.results())
    except Exception as e:
        log.warning("arxiv.fetch_failed", arxiv_id=arxiv_id, error=str(e))
        return None
    if not results:
        return None
    r = results[0]

    authors = [Author(name=a.name) for a in r.authors]
    abstract = r.summary or ""

    paper = Paper(
        paper_id=f"arxiv:{arxiv_id}",
        source=PaperSource.ARXIV,
        title=r.title or arxiv_id,
        authors=authors,
        year=r.published.year if r.published else None,
        venue="arXiv",
        abstract=abstract,
        sections={"abstract": Section(name="abstract", text=abstract)},
        open_access_url=r.pdf_url,
        full_text_available=False,  # we don't fetch PDF body by default
        ingested_at=datetime.now(timezone.utc).isoformat(),
    )
    return paper
