"""Resolve any identifier (DOI, arxiv id, pmc id, raw citation) to a Paper.

Used by the recursive chain resolver to fetch cited papers on demand.
"""

import re

from app.ingest import arxiv_client, openalex_client, pmc_client
from app.ingest.fixtures import try_load_fixture
from app.ingest.pipeline import _index_with_sentences
from app.logging import get_logger
from app.models import Paper, Reference

log = get_logger(__name__)


async def fetch_by_ref(ref: Reference | str) -> Paper | None:
    """`ref` can be a Reference object or a raw string identifier."""
    if isinstance(ref, Reference):
        # Try DOI, arxiv_id, pmc_id, then raw_citation as a last resort
        for ident in [
            f"doi:{ref.doi}" if ref.doi else None,
            f"arxiv:{ref.arxiv_id}" if ref.arxiv_id else None,
            f"pmc:{ref.pmc_id}" if ref.pmc_id else None,
            ref.raw_citation,
        ]:
            if not ident:
                continue
            paper = await _try_resolve(ident)
            if paper is not None:
                return paper
        return None
    return await _try_resolve(ref)


async def _try_resolve(identifier: str) -> Paper | None:
    fix = try_load_fixture(identifier)
    if fix is not None:
        return await _index_with_sentences(fix)

    arxiv_id = arxiv_client.parse_arxiv_id(identifier)
    if arxiv_id:
        paper = arxiv_client.fetch_arxiv(arxiv_id)
        if paper:
            return await _index_with_sentences(paper)

    pmc_id = pmc_client.parse_pmc_id(identifier)
    if pmc_id:
        paper = await pmc_client.fetch_pmc(pmc_id)
        if paper:
            return await _index_with_sentences(paper)

    doi = openalex_client.parse_doi(identifier)
    if doi:
        meta = await openalex_client.fetch_openalex_by_doi(doi)
        if meta:
            from app.ingest.pipeline import _paper_from_openalex

            paper = _paper_from_openalex(doi, meta)
            return await _index_with_sentences(paper)

    return None
