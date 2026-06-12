"""Papers index DAO — indexing, fetching, and reference lookups."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.logging import get_logger
from app.models import Paper, PaperSource, Reference, Section
from app.search.elastic_client import get_es

log = get_logger(__name__)
PAPER_INDEX_VERSION = "4"


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
        "full_text_available": paper.full_text_available,
        "ingest_version": PAPER_INDEX_VERSION,
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


async def get_paper_model(paper_id: str) -> Paper | None:
    doc = await get_paper(paper_id)
    if not doc or doc.get("ingest_version") != PAPER_INDEX_VERSION:
        return None
    return paper_model_from_doc(doc)


def paper_model_from_doc(doc: dict[str, Any]) -> Paper:
    sections: dict[str, Section] = {}
    if doc.get("abstract"):
        sections["abstract"] = Section(name="abstract", text=doc["abstract"])
    if doc.get("methods_text"):
        sections["methods"] = Section(name="methods", text=doc["methods_text"])
    return Paper(
        paper_id=doc["paper_id"],
        source=PaperSource(doc.get("source", PaperSource.UPLOAD.value)),
        title=doc.get("title") or doc["paper_id"],
        authors=doc.get("authors") or [],
        year=doc.get("year"),
        venue=doc.get("venue"),
        abstract=doc.get("abstract"),
        sections=sections,
        references=[Reference.model_validate(r) for r in doc.get("references") or []],
        open_access_url=doc.get("open_access_url"),
        full_text_available=bool(
            doc.get("full_text_available") or doc.get("methods_text")
        ),
        ingested_at=doc.get("ingested_at") or "",
    )


async def find_paper_by_citation(citation: str) -> Paper | None:
    """Resolve a citation against the indexed corpus before external APIs."""
    if not citation.strip():
        return None
    settings = get_settings()
    es = get_es()
    result = await es.search(
        index=settings.elastic_papers_index,
        query={
            "bool": {
                "filter": [{"term": {"ingest_version": PAPER_INDEX_VERSION}}],
                "must": [
                    {
                        "multi_match": {
                            "query": citation,
                            "fields": ["title^4", "abstract"],
                            "type": "best_fields",
                            "minimum_should_match": "60%",
                        }
                    }
                ],
            }
        },
        size=1,
    )
    hits = result.get("hits", {}).get("hits", [])
    return paper_model_from_doc(hits[0]["_source"]) if hits else None


async def sentence_context_windows(
    paper_id: str,
    anchor_ids: list[int],
    *,
    radius: int = 2,
) -> tuple[list[int], str]:
    """Expand Elastic retrieval anchors into ordered, contiguous context."""
    doc = await get_paper(paper_id)
    if not doc:
        return [], ""
    by_id = {
        int(sentence["sentence_id"]): sentence["text"]
        for sentence in doc.get("methods_sentences") or []
    }
    if not anchor_ids:
        return [], ""
    ranked_unique = list(dict.fromkeys(anchor_ids))
    center = max(
        ranked_unique,
        key=lambda candidate: sum(
            abs(candidate - other) <= radius * 2 for other in ranked_unique
        ),
    )
    clustered_anchors = [
        anchor for anchor in ranked_unique if abs(anchor - center) <= radius * 2
    ]
    selected: set[int] = set()
    for anchor in clustered_anchors:
        selected.update(range(anchor - radius, anchor + radius + 1))
    ordered_ids = [sid for sid in sorted(selected) if sid in by_id]
    passage = "\n".join(f"[{sid}] {by_id[sid]}" for sid in ordered_ids)
    return ordered_ids, passage
