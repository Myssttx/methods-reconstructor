"""Hybrid BM25 + dense-vector search with Reciprocal Rank Fusion.

This is the primitive the agent uses everywhere it needs to find specific
sentences in a cited paper that describe a given methodological claim. We
use Elastic for both the BM25 and kNN passes and fuse client-side with RRF
(k=60, standard) — simpler than relying on rank-features and works against
the open-source distribution.
"""

from typing import Any

from app.config import get_settings
from app.logging import get_logger
from app.search.elastic_client import get_es

log = get_logger(__name__)

RRF_K = 60


def _rrf_fuse(rankings: list[list[str]]) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


async def hybrid_sentence_search(
    paper_id: str,
    query_text: str,
    query_vector: list[float],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Find the top-k sentences in a given paper that match the query.

    Runs a BM25 query against `methods_text` (whole-paper match for filtering)
    AND a nested kNN search against `methods_sentences.vector`, then fuses.
    Returns sentence-level hits with text and sentence_id.
    """
    settings = get_settings()
    es = get_es()

    bm25_resp = await es.search(
        index=settings.elastic_papers_index,
        query={
            "bool": {
                "filter": [{"term": {"paper_id": paper_id}}],
                "must": [
                    {
                        "nested": {
                            "path": "methods_sentences",
                            "query": {"match": {"methods_sentences.text": query_text}},
                            "inner_hits": {"size": top_k, "name": "bm25_sentences"},
                            "score_mode": "max",
                        }
                    }
                ],
            }
        },
        size=1,
    )

    knn_resp = await es.search(
        index=settings.elastic_papers_index,
        query={
            "bool": {
                "filter": [{"term": {"paper_id": paper_id}}],
                "must": [
                    {
                        "nested": {
                            "path": "methods_sentences",
                            "query": {
                                "knn": {
                                    "field": "methods_sentences.vector",
                                    "query_vector": query_vector,
                                    "num_candidates": top_k * 5,
                                }
                            },
                            "inner_hits": {"size": top_k, "name": "knn_sentences"},
                            "score_mode": "max",
                        }
                    }
                ],
            }
        },
        size=1,
    )

    bm25_ranking = _extract_sentence_ranking(bm25_resp, "bm25_sentences")
    knn_ranking = _extract_sentence_ranking(knn_resp, "knn_sentences")

    fused = _rrf_fuse([list(bm25_ranking.keys()), list(knn_ranking.keys())])
    merged_sentences = {**bm25_ranking, **knn_ranking}

    return [
        {"sentence_id": int(sid), "text": merged_sentences[sid], "score": score}
        for sid, score in fused[:top_k]
        if sid in merged_sentences
    ]


def _extract_sentence_ranking(resp: dict, inner_hit_name: str) -> dict[str, str]:
    """Pull nested inner_hits into a {sentence_id: text} ordered dict."""
    ordered: dict[str, str] = {}
    for hit in resp.get("hits", {}).get("hits", []):
        nested_hits = hit.get("inner_hits", {}).get(inner_hit_name, {}).get("hits", {}).get("hits", [])
        for nh in nested_hits:
            src = nh["_source"]
            sid = str(src["sentence_id"])
            ordered[sid] = src["text"]
    return ordered


async def hybrid_claim_search(
    query_text: str,
    query_vector: list[float],
    top_k: int = 5,
    filters: dict[str, Any] | None = None,
    exclude_paper_id: str | None = None,
    exclude_paper_prefixes: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Corpus-wide hybrid search over claims (used for partial-claim augmentation)."""
    settings = get_settings()
    es = get_es()

    must_filters: list[dict] = []
    if filters:
        for k, v in filters.items():
            must_filters.append({"term": {k: v}})
    must_not = [{"term": {"paper_id": exclude_paper_id}}] if exclude_paper_id else []
    must_not.extend({"prefix": {"paper_id": prefix}} for prefix in exclude_paper_prefixes)

    bm25_resp = await es.search(
        index=settings.elastic_claims_index,
        query={
            "bool": {
                "must": [{"match": {"raw_text": query_text}}],
                "filter": must_filters,
                "must_not": must_not,
            }
        },
        size=top_k,
    )

    knn_resp = await es.search(
        index=settings.elastic_claims_index,
        knn={
            "field": "embedding",
            "query_vector": query_vector,
            "k": top_k,
            "num_candidates": top_k * 5,
            "filter": {
                "bool": {
                    "filter": must_filters,
                    "must_not": must_not,
                }
            }
            if must_filters or must_not
            else None,
        },
        size=top_k,
    )

    bm25_ids = [h["_id"] for h in bm25_resp["hits"]["hits"]]
    knn_ids = [h["_id"] for h in knn_resp["hits"]["hits"]]

    id_to_source: dict[str, dict] = {}
    for h in bm25_resp["hits"]["hits"] + knn_resp["hits"]["hits"]:
        id_to_source.setdefault(h["_id"], h["_source"])

    fused = _rrf_fuse([bm25_ids, knn_ids])
    return [id_to_source[cid] | {"score": score} for cid, score in fused[:top_k] if cid in id_to_source]
