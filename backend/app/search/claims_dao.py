"""Claims index DAO."""
from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.logging import get_logger
from app.models import Claim
from app.search.elastic_client import get_es

log = get_logger(__name__)


def _claim_doc(claim: Claim, embedding: list[float] | None) -> dict[str, Any]:
    d = claim.model_dump(mode="json")
    if embedding is not None:
        d["embedding"] = embedding
    return d


async def index_claim(claim: Claim, embedding: list[float] | None = None) -> None:
    settings = get_settings()
    es = get_es()
    await es.index(
        index=settings.elastic_claims_index,
        id=claim.claim_id,
        document=_claim_doc(claim, embedding),
        refresh="wait_for",
    )


async def bulk_index_claims(claims: list[Claim], embeddings: list[list[float]] | None = None) -> None:
    settings = get_settings()
    es = get_es()
    ops: list[dict] = []
    for i, claim in enumerate(claims):
        emb = embeddings[i] if embeddings else None
        ops.append({"index": {"_index": settings.elastic_claims_index, "_id": claim.claim_id}})
        ops.append(_claim_doc(claim, emb))
    if not ops:
        return
    resp = await es.bulk(operations=ops, refresh="wait_for")
    if resp.get("errors"):
        failed = [
            item for item in resp.get("items", [])
            if "error" in item.get("index", {})
        ]
        log.error("claims.bulk_index_errors", n_failed=len(failed), sample=failed[:3])
        raise RuntimeError(f"Elasticsearch bulk index had {len(failed)} failures")
    log.info("claims.bulk_indexed", n=len(claims))


async def delete_claims_for_paper(paper_id: str) -> None:
    """Replace a paper's claim set instead of accumulating duplicate runs."""
    settings = get_settings()
    es = get_es()
    await es.delete_by_query(
        index=settings.elastic_claims_index,
        query={"term": {"paper_id": paper_id}},
        conflicts="proceed",
        refresh=True,
    )


async def claims_for_paper(paper_id: str) -> list[dict[str, Any]]:
    settings = get_settings()
    es = get_es()
    result = await es.search(
        index=settings.elastic_claims_index,
        query={"term": {"paper_id": paper_id}},
        size=10_000,
    )
    return [hit["_source"] for hit in result["hits"]["hits"]]
