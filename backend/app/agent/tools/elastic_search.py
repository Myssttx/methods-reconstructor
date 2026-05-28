"""Thin wrapper exposed as an agent-callable tool name (matches the spec)."""

from typing import Any

from app.llm.embeddings import embed_text
from app.search.hybrid_search import hybrid_claim_search


async def elastic_search(
    query: str,
    *,
    index: str = "claims",
    filters: dict[str, Any] | None = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    if index != "claims":
        raise ValueError("elastic_search tool only exposes the claims index; "
                         "use methods_locator for paper-internal searches.")
    return await hybrid_claim_search(query, embed_text(query), top_k=top_k, filters=filters)
