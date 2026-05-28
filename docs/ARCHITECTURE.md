# Architecture

## Topology

```
┌──────────────┐      ┌──────────────────────┐      ┌──────────────────┐
│  Next.js 14  │──▶──│   FastAPI backend    │─▶────│  Elasticsearch   │
│  (SSE consumer)│   │   - Agent runner     │      │  papers + claims │
└──────────────┘    │   - Recursive loop   │      │  hybrid retrieval│
                    └──────────┬───────────┘      └──────────────────┘
                               │
              ┌────────────────┼────────────────────────────────────┐
              ▼                ▼                                    ▼
        ┌──────────┐    ┌────────────────┐                  ┌──────────────┐
        │ Gemini / │    │ External APIs  │                  │  Storage     │
        │ Claude / │    │ arXiv, PMC,    │                  │  FS or       │
        │ offline  │    │ OpenAlex,      │                  │  Firestore   │
        │ mock     │    │ Crossref, S2   │                  │  + GCS       │
        └──────────┘    └────────────────┘                  └──────────────┘
```

## Why Elastic is essential

Three points in the agent loop *require* Elastic's specific capabilities:

1. **`methods_locator`** — given a methodological claim, find the exact sentences in a cited paper that match it. Implemented as a nested BM25 query on `methods_sentences.text` AND a nested kNN query on `methods_sentences.vector`, fused with Reciprocal Rank Fusion. See [hybrid_search.py](../backend/app/search/hybrid_search.py).

2. **Claims as a structured corpus** — each claim has keyword fields (type, specificity, resolution_status), text fields, and a dense vector embedding. Hybrid claim search powers partial-claim augmentation and the "what does standard mean in this subfield" lookup.

3. **Citation-graph aggregations** — *(future)* "how many papers cite paper X for method Y?" is an Elastic aggregation, not a retrieval query.

The local stack runs real Elasticsearch 8.15 via `docker-compose`. Switch to Elastic Cloud by setting `ELASTIC_CLOUD_ID` and `ELASTIC_API_KEY` — same client, same mappings.

## The recursive resolver

[`chain_resolve.py`](../backend/app/agent/tools/chain_resolve.py) is the core IP.

For each claim with `specificity == shortcut_citation`:
1. Look up the cited reference(s) on the source paper.
2. Fetch each cited paper (Elastic if already indexed, external APIs otherwise).
3. Call `methods_locator(cited_paper, claim)` — this is the Elastic hybrid query.
4. Ask Gemini Flash whether the located passage **fully describes** the procedure, or **is itself a shortcut** to a yet-deeper paper.
5. If shortcut: build a synthetic sub-claim and **recurse**, with `depth += 1`.
6. Hard depth cap of 5. Terminal gaps surface with a reason and a suggested action.

Every step appends to a `resolution_chain` so the UI can show the full provenance back to the source sentence.

## Offline mode

The product runs end-to-end with **no cloud credentials**:

- LLM: deterministic `OfflineLLM` mock that returns structured plausible JSON
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- Storage: `LocalFileStore` writing JSON under `./.local_storage`
- Elastic: still real (local container) — Elastic is too central to mock

Add `GOOGLE_API_KEY` or `ANTHROPIC_API_KEY` to upgrade. The OfflineLLM is also what the unit tests rely on, so behavior stays deterministic.

## Data flow per request

```
POST /api/reconstructions          ─▶ start_job() creates AgentRunner, schedules task
GET  /api/reconstructions/:id/stream ─▶ SSE attaches to runner's async queue

  ingest_identifier()                          ─▶ Paper, indexed into Elastic papers
  extract_claims()              (Gemini Pro)   ─▶ Claim[]
  bulk_index_claims()                          ─▶ claims indexed (with embeddings)
  for c in claims:
    resolve_claim(c, paper)                    ─▶ chain.fetching events → ResolutionResult
    index_claim(c) (updated)
  assemble(paper, claims)        (Gemini Pro)  ─▶ ReconstructedProtocol
  store.put_reconstruction()                   ─▶ persisted, available via /protocol

GET  /api/reconstructions/:id/protocol        ─▶ ReconstructedProtocol JSON
GET  /api/reconstructions/:id/export.{json|md|csv} ─▶ download
```

## File map

| Concern | Where |
|---|---|
| HTTP + SSE | `backend/app/api/routes_*.py` |
| Agent orchestrator | `backend/app/agent/runner.py` |
| Recursive resolver (core IP) | `backend/app/agent/tools/chain_resolve.py` |
| Elastic hybrid search | `backend/app/search/hybrid_search.py` |
| LLM provider abstraction | `backend/app/llm/gemini_client.py` |
| Paper ingest pipeline | `backend/app/ingest/pipeline.py` |
| Index mappings | `infra/elastic/{papers,claims}_index.json` |
| Pydantic shapes | `backend/app/models/` |
| Frontend pages | `frontend/src/app/` |
| Frontend components | `frontend/src/components/` |
