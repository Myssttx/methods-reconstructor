from __future__ import annotations
"""Thin wrapper exposed as an agent-callable tool name (matches the spec)."""

from typing import Any, Optional

from app.llm.embeddings import aembed_text
from app.search.hybrid_search import hybrid_claim_search


async def elastic_search(
    query: str,
    *,
    index: str = "claims",
    filters: Optional[dict[str, Any]] = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    if index != "claims":
        raise ValueError(
            "elastic_search tool only exposes the claims index; "
            "use methods_locator for paper-internal searches."
        )
    vector = await aembed_text(query)
    return await hybrid_claim_search(query, vector, top_k=top_k, filters=filters)
