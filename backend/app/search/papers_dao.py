"""Papers index DAO — indexing, fetching, and reference lookups."""

from typing import Any

from app.config import get_settings
from app.logging import get_logger
from app.models import Paper
from app.search.elastic_client import get_es

log = get_logger(__name__)


async def index_paper(paper: Paper, sentences: list[dict[str, Any]]) -> None:
    """
    Index a paper document.

    `sentences` is a list of {sentence_id, text, vector} dicts; vectors must
    match the dim configured in infra/elastic/papers_index.json.
    """
    settings = get_settings()
    es = get_es()

    methods_text = paper.methods_text()

    body = {
        "paper_id": paper.paper_id,
        "source": paper.source.value,
        "title": paper.title,
        "authors": [a.model_dump() for a in paper.authors],
        "year": paper.year,
        "venue": paper.venue,
        "abstract": paper.abstract,
        "methods_text": methods_text,
        "methods_sentences": sentences,
        "references": [r.model_dump() for r in paper.references],
        "open_access_url": paper.open_access_url,
        "ingested_at": paper.ingested_at,
    }

    await es.index(
        index=settings.elastic_papers_index,
        id=paper.paper_id,
        document=body,
        refresh="wait_for",
    )
    log.info("paper.indexed", paper_id=paper.paper_id, n_sentences=len(sentences))


async def get_paper(paper_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    es = get_es()
    try:
        result = await es.get(index=settings.elastic_papers_index, id=paper_id)
        return result["_source"]
    except Exception:
        return None


async def paper_exists(paper_id: str) -> bool:
    settings = get_settings()
    es = get_es()
    return bool(await es.exists(index=settings.elastic_papers_index, id=paper_id))
