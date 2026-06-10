"""Google ADK tools backed by the production reconstruction pipeline."""

import uuid
from typing import Any

from app.agent.runner import AgentRunner
from app.agent.tools.elastic_search import elastic_search
from app.storage.firestore_client import get_store


def plan_reconstruction(identifier: str) -> dict[str, Any]:
    """Return the observable research plan used for one paper."""
    return {
        "identifier": identifier,
        "objective": (
            "Reconstruct the paper's cancer-research methodology with traceable "
            "sentence and citation evidence."
        ),
        "steps": [
            "Resolve the DOI, PMC ID, URL, or PDF and parse the methods section.",
            "Index paper text, sentence vectors, references, and claims in Elastic.",
            "Decompose the methods into source-linked methodological claims.",
            "Use Elastic BM25 plus vector retrieval to locate cited method evidence.",
            "Follow citation shortcuts recursively and record the evidence chain.",
            "Assemble a reproducible methods reconstruction and explicit gap report.",
        ],
        "search_layer": "Elastic papers and claims indexes with hybrid retrieval",
        "model_layer": "Gemini on Vertex AI with deterministic bounded fallbacks",
    }


async def reconstruct_cancer_methods(identifier: str) -> dict[str, Any]:
    """Run the full reconstruction and return a concise result manifest."""
    job_id = f"adk-{uuid.uuid4()}"
    runner = AgentRunner(
        job_id=job_id,
        identifier=identifier,
        reuse_cached_claims=True,
    )
    await runner.run()

    store = get_store()
    job = await store.get_job(job_id) or {}
    if job.get("status") != "complete" or not job.get("protocol_id"):
        return {
            "job_id": job_id,
            "status": job.get("status") or "failed",
            "error": job.get("error") or "Reconstruction did not complete",
        }

    protocol = await store.get_reconstruction(job["protocol_id"]) or {}
    section_counts = {
        section: len(claims)
        for section, claims in (protocol.get("sections") or {}).items()
    }
    return {
        "job_id": job_id,
        "protocol_id": job["protocol_id"],
        "status": "complete",
        "title": protocol.get("title"),
        "source_paper_id": protocol.get("source_paper_id"),
        "methods_evidence_score": protocol.get("methods_evidence_score"),
        "section_claim_counts": section_counts,
        "gap_count": len(protocol.get("gaps") or []),
        "timings_ms": job.get("timings_ms") or {},
        "generation_metadata": protocol.get("generation_metadata") or {},
        "protocol_endpoint": f"/api/reconstructions/{job_id}/protocol",
        "pdf_endpoint": f"/api/reconstructions/{job_id}/export.pdf",
    }


async def search_elastic_evidence(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search indexed methodological evidence using Elastic hybrid retrieval."""
    bounded_top_k = max(1, min(top_k, 20))
    hits = await elastic_search(query, top_k=bounded_top_k)
    return {
        "query": query,
        "search": "Elastic BM25 plus dense-vector retrieval with RRF",
        "hits": [
            {
                "paper_id": hit.get("paper_id"),
                "claim_id": hit.get("claim_id"),
                "type": hit.get("type"),
                "specificity": hit.get("specificity"),
                "resolution_status": hit.get("resolution_status"),
                "text": hit.get("resolved_text") or hit.get("raw_text"),
                "score": hit.get("score"),
            }
            for hit in hits
        ],
    }


async def read_reconstruction(
    protocol_id: str,
    section: str = "",
    offset: int = 0,
    limit: int = 10,
) -> dict[str, Any]:
    """Read a bounded page from a persisted methods reconstruction."""
    protocol = await get_store().get_reconstruction(protocol_id)
    if protocol is None:
        return {"error": "Protocol not found", "protocol_id": protocol_id}

    bounded_offset = max(0, offset)
    bounded_limit = max(1, min(limit, 25))
    sections = protocol.get("sections") or {}
    selected_sections = [section] if section and section in sections else list(sections)
    claims = [
        {
            "section": section_name,
            "claim_id": claim.get("claim_id"),
            "text": claim.get("resolved_text") or claim.get("raw_text"),
            "resolution_status": claim.get("resolution_status"),
            "source_sentence_id": claim.get("raw_sentence_id"),
            "evidence_chain": claim.get("resolution_chain") or [],
        }
        for section_name in selected_sections
        for claim in sections.get(section_name, [])
    ]
    page = claims[bounded_offset : bounded_offset + bounded_limit]
    return {
        "protocol_id": protocol_id,
        "title": protocol.get("title"),
        "methods_evidence_score": protocol.get("methods_evidence_score"),
        "available_sections": list(sections),
        "offset": bounded_offset,
        "limit": bounded_limit,
        "total_claims": len(claims),
        "claims": page,
        "gaps": (protocol.get("gaps") or [])[:bounded_limit] if not section else [],
    }
