import asyncio

import pytest

from app.agent.tools import paper_fetch
from app.agent.tools.paper_fetch import (
    FetchResult,
    PaperFetchSession,
    _citation_matches_title,
)
from app.ingest.crossref_client import _citation_contains_title
from app.models import Paper, PaperSource, Reference


def test_citation_title_identity_requires_substantial_overlap():
    citation = (
        "Jackson HW et al. The single-cell pathology landscape of breast cancer. "
        "Nature 578, 615-620 (2020)."
    )
    title = "The single-cell pathology landscape of breast cancer"

    assert _citation_matches_title(citation, title)
    assert _citation_contains_title(citation, title)
    assert not _citation_matches_title(citation, "Unrelated protein folding methods")


@pytest.mark.asyncio
async def test_fetch_session_deduplicates_concurrent_reference_fetches(monkeypatch):
    calls = 0
    paper = Paper(
        paper_id="doi:10.1000/cited",
        source=PaperSource.OPENALEX,
        title="Cited paper",
    )

    async def fake_fetch(_ref):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return FetchResult(paper=paper)

    monkeypatch.setattr(paper_fetch, "fetch_by_ref", fake_fetch)
    session = PaperFetchSession()
    ref = Reference(
        ref_id="b1",
        raw_citation="Cited paper",
        doi="10.1000/cited",
    )

    first, second = await asyncio.gather(session.fetch(ref), session.fetch(ref))

    assert calls == 1
    assert first.paper == paper
    assert second.paper == paper
