# Methods Reconstructor

An agent that turns shortcut-citation-riddled scientific methods sections into
evidence-backed methods packets and flags exactly where the citation chain breaks.

Built for the **Google Cloud Rapid Agent Hackathon — Elastic Track**.

---

## What it does

You paste a paper (arXiv URL, DOI, PMC ID, or PDF). The agent:

1. **Ingests** the paper and indexes it into Elastic (full text, methods sentences with vector embeddings, references)
2. **Decomposes** the methods section into structured methodological claims
3. **Recursively resolves** every "as described in Smith et al. 2019" shortcut by fetching the cited paper, locating the actual procedure via Elastic hybrid search, and recursing if that paper *also* shortcuts (up to a depth cap of 5)
4. **Assembles** a methods packet with sentence-level provenance and clearly marked corpus inferences
5. **Reports gaps** — every claim it couldn't resolve, why, and what to do next
6. **Reports methods evidence coverage** — not a claim that the experiment itself is reproducible

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

1. **Canonical paper cache** — parsed methods, references, sentence IDs, embeddings, and parser version live in the papers index. Repeated runs reuse this evidence.
2. **Hybrid sentence-level retrieval** — BM25 and dense-vector rankings are fused with RRF, then expanded into one ordered, contiguous context window from the indexed paper.
3. **Structured claim corpus** — claims have keyword, text, provenance, status, and vector fields. Repeated runs replace the paper's claim set instead of accumulating duplicates.
4. **Citation-graph analytics** — future corpus-level method-dependency analysis can use Elastic aggregations over the same evidence store.

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

This is a research prototype, not a validated reproducibility assessor. It validates
structured LLM output, rejects fabricated source spans, distinguishes evidence-backed
resolution from corpus inference, enforces job limits, and persists completed results.
The local worker registry is still process-local; production deployment needs a durable
queue for jobs that must survive worker restarts.

## License

Apache 2.0 — see [LICENSE](LICENSE).
