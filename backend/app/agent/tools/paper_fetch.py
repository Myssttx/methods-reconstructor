"""Resolve a citation to an Elasticsearch-indexed paper with methods text."""

import re
from dataclasses import dataclass

from app.ingest import crossref_client
from app.ingest.pipeline import ingest_identifier
from app.logging import get_logger
from app.models import GapReason, Paper, Reference
from app.search.papers_dao import find_paper_by_citation

log = get_logger(__name__)


@dataclass
class FetchResult:
    paper: Paper | None
    failure_reason: GapReason | None = None


async def fetch_by_ref(ref: Reference | str) -> FetchResult:
    """Resolve from Elastic first, then canonical external sources."""
    if isinstance(ref, str):
        paper = await ingest_identifier(ref)
        if paper and paper.methods_text():
            return FetchResult(paper=paper)
        return FetchResult(
            paper=None,
            failure_reason=(
                GapReason.SOURCE_UNAVAILABLE if paper else GapReason.REFERENCE_UNRESOLVED
            ),
        )

    identifiers = [
        f"doi:{ref.doi}" if ref.doi else None,
        f"arxiv:{ref.arxiv_id}" if ref.arxiv_id else None,
        f"pmc:{ref.pmc_id}" if ref.pmc_id else None,
    ]
    found_metadata = False
    for identifier in identifiers:
        if not identifier:
            continue
        paper = await ingest_identifier(identifier)
        if paper is not None:
            found_metadata = True
        if paper and paper.methods_text():
            return FetchResult(paper=paper)

    citation = ref.title or ref.raw_citation
    indexed = await find_paper_by_citation(citation)
    if (
        indexed
        and indexed.methods_text()
        and _citation_matches_title(citation, indexed.title)
    ):
        log.info("paper_fetch.elastic_citation_hit", paper_id=indexed.paper_id)
        return FetchResult(paper=indexed)

    doi = await crossref_client.resolve_citation(citation)
    if doi:
        paper = await ingest_identifier(f"doi:{doi}")
        if paper is not None:
            found_metadata = True
        if paper and paper.methods_text():
            return FetchResult(paper=paper)

    return FetchResult(
        paper=None,
        failure_reason=(
            GapReason.SOURCE_UNAVAILABLE
            if found_metadata
            else GapReason.REFERENCE_UNRESOLVED
        ),
    )


def _citation_matches_title(citation: str, title: str) -> bool:
    title_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", title.casefold())
        if len(token) >= 4
    }
    if not title_tokens:
        return False
    citation_tokens = set(re.findall(r"[a-z0-9]+", citation.casefold()))
    return len(title_tokens & citation_tokens) / len(title_tokens) >= 0.6
