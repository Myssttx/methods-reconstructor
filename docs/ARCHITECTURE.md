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

1. **Canonical paper evidence store** — parsed methods, references, parser version,
   sentence IDs, and sentence embeddings are stored in the papers index. Cited-paper
   resolution checks Elastic before external APIs.

2. **`methods_locator`** — nested BM25 and kNN rankings over
   `methods_sentences` are fused with RRF. Retrieval anchors are expanded from the
   indexed paper into one dense, ordered context window.

3. **Claims as a structured corpus** — each run replaces that paper's deterministic
   claim IDs. Hybrid claim search may suggest completions, but those remain
   `inferred` and do not count as evidence-backed.

4. **Citation-graph aggregations** — *(future)* "how many papers cite paper X for
   method Y?" is an Elastic aggregation, not a retrieval query.

The local stack runs real Elasticsearch 8.15 via `docker-compose`. Switch to Elastic Cloud by setting `ELASTIC_CLOUD_ID` and `ELASTIC_API_KEY` — same client, same mappings.

## The recursive resolver

[`chain_resolve.py`](../backend/app/agent/tools/chain_resolve.py) is the core IP.

For each claim with `specificity == shortcut_citation`:
1. Look up the cited reference(s) on the source paper.
2. Fetch each cited paper (Elastic if already indexed, external APIs otherwise).
3. Call `methods_locator(cited_paper, claim)` — this is the Elastic hybrid query.
4. Ask Gemini Flash whether the located passage **fully describes** the procedure, or **is itself a shortcut** to a yet-deeper paper.
5. If shortcut: build a synthetic sub-claim and **recurse**, with `depth += 1`.
6. Hard depth cap of 5, per-job timeout, and approximate token budget.
7. Terminal gaps distinguish unresolved references, unavailable full text, and no match.

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
GET  /api/reconstructions/:id/stream ─▶ replayable fan-out SSE stream

  ingest_identifier()                          ─▶ Paper, indexed into Elastic papers
  extract_claims()              (Gemini Pro)   ─▶ Claim[]
  delete_claims_for_paper()                    ─▶ remove stale claim set
  bulk_index_claims()                          ─▶ claims indexed (with embeddings)
  bounded gather(resolve_claim(...))           ─▶ recursive Elastic retrieval
  bulk_index_claims()                          ─▶ final statuses + provenance
  assemble(paper, claims)        (Gemini Pro)  ─▶ ReconstructedProtocol
  store.put_reconstruction()                   ─▶ persisted, available via /protocol

GET  /api/reconstructions/:id/protocol        ─▶ ReconstructedProtocol JSON
GET  /api/reconstructions/:id/export.{json|md|csv} ─▶ download
```

`methods_evidence_score` is the percentage of extracted claims backed by original
source text or sentence-level cited-paper evidence. It is not an experimental
reproducibility score. `reproducibility_score` remains only as a compatibility field.

## Deployment boundary

Completed jobs and protocols are persisted, and completed pages can reload without a
live runner. Active execution is still process-local. Production should place
`AgentRunner.run()` behind a durable queue such as Cloud Tasks before enabling
multi-instance autoscaling.

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
