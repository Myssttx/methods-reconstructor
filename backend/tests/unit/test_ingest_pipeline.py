from datetime import timezone, datetime, timedelta

import pytest

from app.ingest import pipeline
from app.models import Paper, PaperSource


def _metadata_only_paper(*, ingested_at: str) -> Paper:
    return Paper(
        paper_id="doi:10.1000/unavailable",
        source=PaperSource.OPENALEX,
        title="Metadata-only paper",
        ingested_at=ingested_at,
    )


@pytest.mark.asyncio
async def test_recent_metadata_only_result_skips_repeated_acquisition(monkeypatch):
    cached = _metadata_only_paper(ingested_at=datetime.now(timezone.utc).isoformat())
    fetch_called = False

    async def fake_get(_paper_id):
        return cached

    async def unexpected_fetch():
        nonlocal fetch_called
        fetch_called = True
        return None

    monkeypatch.setattr(pipeline, "get_paper_model", fake_get)

    result = await pipeline._ingest_canonical(cached.paper_id, unexpected_fetch)

    assert result == cached
    assert not fetch_called


@pytest.mark.asyncio
async def test_stale_metadata_only_result_is_retried(monkeypatch):
    cached = _metadata_only_paper(
        ingested_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    )
    refreshed = _metadata_only_paper(ingested_at=datetime.now(timezone.utc).isoformat())
    indexed: list[Paper] = []

    async def fake_get(_paper_id):
        return cached

    async def fake_fetch():
        return refreshed

    async def fake_index(paper):
        indexed.append(paper)
        return paper

    monkeypatch.setattr(pipeline, "get_paper_model", fake_get)
    monkeypatch.setattr(pipeline, "_index_with_sentences", fake_index)
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type("Settings", (), {"app_negative_acquisition_cache_seconds": 60})(),
    )

    result = await pipeline._ingest_canonical(cached.paper_id, fake_fetch)

    assert result == refreshed
    assert indexed == [refreshed]
