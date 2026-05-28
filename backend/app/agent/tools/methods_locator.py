"""Given (cited_paper, claim), find the specific sentences in the cited paper's
methods section that describe the procedure being referenced.

This is the place Elastic's hybrid (BM25 + dense vector) retrieval is the core
primitive — without it you either retrieve too many irrelevant sentences (vector
only on a noisy corpus) or miss paraphrased techniques entirely (BM25 only).
"""

import json

from app.agent.prompts import METHODS_LOCATOR_SYSTEM, METHODS_LOCATOR_USER
from app.agent.schemas import LocatorResult
from app.llm.embeddings import embed_text
from app.llm.gemini_client import get_llm
from app.logging import get_logger
from app.models import Claim, Paper
from app.search.hybrid_search import hybrid_sentence_search

log = get_logger(__name__)


async def locate(ref_paper: Paper, claim: Claim, top_k: int = 8) -> LocatorResult:
    query_vector = embed_text(claim.raw_text)

    hits = await hybrid_sentence_search(
        paper_id=ref_paper.paper_id,
        query_text=claim.raw_text,
        query_vector=query_vector,
        top_k=top_k,
    )

    if not hits:
        log.info("locator.no_hits", paper_id=ref_paper.paper_id, claim_id=claim.claim_id)
        return LocatorResult(fully_describes=False, is_itself_shortcut=False)

    sentence_ids = [h["sentence_id"] for h in hits]
    passage_text = "\n".join(h["text"] for h in hits)

    user = METHODS_LOCATOR_USER.format(
        claim_raw_text=claim.raw_text,
        ref_paper_id=ref_paper.paper_id,
        passage_text=passage_text,
    )
    llm = get_llm()
    resp = await llm.complete(prompt=user, system=METHODS_LOCATOR_SYSTEM, model="flash")

    try:
        data = json.loads(resp)
    except json.JSONDecodeError:
        log.warning("locator.bad_json", preview=resp[:200])
        return LocatorResult(
            fully_describes=False,
            is_itself_shortcut=False,
            passage_text=passage_text,
            sentence_ids=sentence_ids,
        )

    return LocatorResult(
        fully_describes=bool(data.get("fully_describes", False)),
        is_itself_shortcut=bool(data.get("is_itself_shortcut", False)),
        new_cited_refs=list(data.get("new_cited_refs", [])),
        passage_text=passage_text,
        sentence_ids=sentence_ids,
    )
