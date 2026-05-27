# Methods Reconstructor

An agent that turns shortcut-citation-riddled scientific methods sections into self-contained, reproducible protocols — and flags exactly where the chain breaks.

Built for the **Google Cloud Rapid Agent Hackathon — Elastic Track**.

---

## What it does

You paste a paper (arXiv URL, DOI, PMC ID, or PDF). The agent:

1. **Ingests** the paper and indexes it into Elastic (full text, methods sentences with vector embeddings, references)
2. **Decomposes** the methods section into structured methodological claims
3. **Recursively resolves** every "as described in Smith et al. 2019" shortcut by fetching the cited paper, locating the actual procedure via Elastic hybrid search, and recursing if that paper *also* shortcuts (up to a depth cap of 5)
4. **Assembles** a reconstructed protocol with full provenance (every claim links back to the source sentence)
5. **Reports gaps** — every claim it couldn't resolve, why, and what to do next

The defensible primitive is the **recursive citation-chain resolver + Elastic hybrid retrieval** combined. A vanilla single-shot RAG can't do this.

## Architecture

```
┌──────────────┐    ┌───────────────────┐    ┌─────────────────┐
│  Next.js UI  │ ─▶ │  FastAPI agent    │ ─▶ │  Elastic Cloud  │
│  (SSE live)  │    │  (recursive loop) │    │  papers+claims  │
└──────────────┘    └──────────┬────────┘    └─────────────────┘
                               │
                               ├─▶ Gemini 2.5 Pro / Flash (planning, extraction)
                               ├─▶ arXiv / PMC / OpenAlex / Crossref / Unpaywall
                               └─▶ GROBID (PDF → TEI XML, optional)
```

Full spec: [docs/BUILD_SPEC.md](docs/BUILD_SPEC.md). Product brief: [docs/PRD.md](docs/PRD.md).

## Elastic is essential

This product exists because **Elastic does the heavy lifting** at three points the agent loop can't shortcut:

1. **Hybrid sentence-level retrieval** — given a methodological claim, find the *exact* sentences in a cited paper that describe it. BM25 alone misses paraphrased techniques; vectors alone return vaguely-related content. Elastic's hybrid (BM25 + dense vectors + RRF) is the right primitive.
2. **Claim corpus as a structured index** — claims have keyword fields (type, specificity, resolution_status), text fields (raw_text, resolved_text), and dense vectors. Elastic handles all three natively in one index.
3. **Citation-graph aggregations** — "how many papers cite paper X for method Y?" is an aggregation, not a retrieval. Elastic aggs make this fast at corpus scale.

The local stack runs a real Elasticsearch 8.15 node via `docker-compose`. Production swaps that for Elastic Cloud — same client, same mappings.

## Quick start (local, no cloud credentials needed)

```bash
git clone <repo>
cd methods-reconstructor
cp .env.example .env
make dev                 # brings up elastic, redis, backend, frontend
# in another shell:
make elastic-init        # creates papers + claims indexes
make seed                # loads demo fixtures
```

Then open http://localhost:3000.

By default the LLM provider is **`offline`** — a deterministic mock returns structured plausible output so the demo runs without any API keys. To use real LLMs, set `GOOGLE_API_KEY` (Gemini) or `ANTHROPIC_API_KEY` (Claude) in `.env`.

## Repo layout

```
backend/    FastAPI + agent loop + Elastic clients + ingest pipeline
frontend/   Next.js 14 App Router, Tailwind, shadcn/ui-style components
infra/      Elastic index mappings, bootstrap scripts, deploy configs
docs/       PRD + build spec
eval/       Held-out eval set + harness
```

## Status

This is an early prototype. The directory shape, Elastic mappings, agent loop, and prompts match the build spec verbatim. Cloud deploy paths (Cloud Run, Firestore, Vertex AI) are scaffolded but require real GCP credentials to exercise — the local stack provides drop-in fallbacks (file-based job store, sentence-transformers embeddings, offline LLM).

## License

Apache 2.0 — see [LICENSE](LICENSE).
