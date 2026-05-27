# Methods Reconstructor — Claude Code Build Specification

**This document is the complete implementation spec. Read it top to bottom before writing any code. Every decision is pre-made; do not improvise infrastructure choices, library versions, or architectural patterns. If something is ambiguous, ask the human; do not guess.**

---

## 0. How to use this document

You are Claude Code. Your job is to build the Methods Reconstructor described in this spec.

**Rules of engagement:**

1. Work in the order given in Section 14 (Build Order). Do not jump ahead.
2. After completing each numbered task in Section 14, stop and confirm with the human before proceeding.
3. Use the exact library versions in Section 3. Do not upgrade or substitute.
4. Use the exact file paths and module names in Section 4. Do not reorganize.
5. Use the exact prompts in Section 9. You may suggest refinements but do not change them silently.
6. All secrets go in `.env`, never committed. A `.env.example` lives in the repo.
7. Write tests as you go. The test commands in Section 13 must pass before each commit.
8. Commit after every successful task in Section 14 with a conventional commit message.

**Before writing any code, read the PRD at `docs/PRD.md` so you understand the product.**

---

## 1. Project Overview

**Product name:** Methods Reconstructor

**One-line:** An agent that takes a scientific paper, recursively resolves every "as described in Smith et al." shortcut citation in its methods section, and produces a self-contained reproducible protocol with a gap report for everything that could not be resolved.

**Submission target:** Google Cloud Rapid Agent Hackathon, Elastic Track. Final code must be in a public GitHub repo with an OSI-approved open-source license (we use Apache 2.0). The repo must contain everything a judge needs to run the project locally or in a fresh GCP project.

**Required integrations (per hackathon rules):**
- **Google Cloud Agent Builder + Gemini models** (mandatory)
- **Elastic Cloud** (the track partner; the integration must be essential, not bolted on)

---

## 2. Architecture (Final, Non-Negotiable)

```
┌─────────────────────────────────────────────────────────┐
│  frontend/  (Next.js 14 App Router on Cloud Run)        │
│    - Input screen, live agent progress, protocol view   │
│    - SSE consumer for streaming updates                 │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS / SSE
                       ▼
┌─────────────────────────────────────────────────────────┐
│  backend/  (FastAPI on Cloud Run)                       │
│    - REST endpoints + SSE streaming                     │
│    - Job orchestration                                  │
│    - Agent runner                                       │
└──────┬───────────┬───────────────┬─────────────────────┘
       │           │               │
       ▼           ▼               ▼
┌───────────┐ ┌──────────┐ ┌─────────────────────────┐
│ Vertex AI │ │ Elastic  │ │ External APIs           │
│ Gemini    │ │ Cloud    │ │ OpenAlex, arXiv,        │
│ 2.5 Pro / │ │ (search  │ │ PMC, Crossref,          │
│ Flash     │ │ + vectors│ │ Unpaywall, Semantic     │
│           │ │ + aggs)  │ │ Scholar, GROBID         │
└───────────┘ └──────────┘ └─────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  Firestore (job metadata, reconstruction history)       │
│  Cloud Storage (PDFs, exports)                          │
│  Memorystore Redis (hot cache, optional MVP)            │
└─────────────────────────────────────────────────────────┘
```

**Why each piece exists:**

- **Next.js frontend** — needs interactivity (streaming progress, drill-down provenance, gap report drawer). Tailwind + shadcn/ui for components.
- **FastAPI backend** — clean async semantics for the agent loop and SSE streaming. Python because all the AI/ML/scientific tooling lives there.
- **Vertex AI Gemini** — required by hackathon. Use Gemini 2.5 Pro for planning + complex reasoning, Gemini 2.5 Flash for high-volume sub-tasks (sentence classification, claim extraction).
- **Elastic Cloud** — the partner integration. Hybrid search (BM25 + dense vectors) on methods sentences, structured fields on claims, aggregations for citation graph queries.
- **Firestore** — job state, user history, exported artifacts metadata.
- **Cloud Storage** — uploaded PDFs, exported protocol artifacts.
- **GROBID** — runs as a sidecar container on Cloud Run for PDF→TEI XML conversion when we can't get clean XML from arXiv/PMC.

---

## 3. Stack and Pinned Versions

### Backend (Python 3.11)

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.9.2
pydantic-settings==2.6.0
httpx==0.27.2
google-cloud-aiplatform==1.71.0
google-genai==0.3.0
google-cloud-firestore==2.19.0
google-cloud-storage==2.18.2
elasticsearch==8.15.1
sentence-transformers==3.2.0
sse-starlette==2.1.3
tenacity==9.0.0
python-multipart==0.0.12
beautifulsoup4==4.12.3
lxml==5.3.0
arxiv==2.1.3
crossrefapi==1.6.0
redis==5.1.1
structlog==24.4.0
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-mock==3.14.0
ruff==0.7.0
mypy==1.13.0
```

### Frontend (Node 20)

```json
{
  "next": "14.2.15",
  "react": "18.3.1",
  "react-dom": "18.3.1",
  "typescript": "5.6.3",
  "tailwindcss": "3.4.13",
  "@radix-ui/react-dialog": "1.1.2",
  "@radix-ui/react-tabs": "1.1.1",
  "@radix-ui/react-tooltip": "1.1.3",
  "lucide-react": "0.453.0",
  "recharts": "2.13.0",
  "clsx": "2.1.1",
  "tailwind-merge": "2.5.4",
  "zod": "3.23.8"
}
```

### Infra

- Cloud Run (managed, region `us-central1`)
- Elastic Cloud on Google Cloud, `us-central1`, smallest hot tier with vector support
- Firestore Native mode
- Cloud Storage standard class, single-region `us-central1`
- Vertex AI in `us-central1`
- GROBID v0.8.1 official Docker image

---

## 4. Repository Layout (Exact)

```
methods-reconstructor/
├── README.md
├── LICENSE                          # Apache 2.0
├── .gitignore
├── .env.example
├── docker-compose.yml               # Local dev: backend + GROBID + Redis
├── Makefile                         # make dev, make test, make deploy, make eval
├── docs/
│   ├── PRD.md                       # The product PRD
│   ├── BUILD_SPEC.md                # This document
│   ├── ARCHITECTURE.md              # Detailed architecture
│   ├── PROMPTS.md                   # All LLM prompts (source of truth)
│   └── DEMO_SCRIPT.md               # Video script
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app entrypoint
│   │   ├── config.py                # pydantic Settings
│   │   ├── logging.py               # structlog setup
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes_papers.py     # POST /papers/ingest, GET /papers/{id}
│   │   │   ├── routes_reconstructions.py  # POST /reconstructions, GET, SSE
│   │   │   ├── routes_exports.py    # GET /reconstructions/{id}/export.{fmt}
│   │   │   └── deps.py              # FastAPI dependencies
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── runner.py            # Orchestrates the full agent loop
│   │   │   ├── planner.py           # Gemini Pro planning calls
│   │   │   ├── tools/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── paper_fetch.py
│   │   │   │   ├── paper_parse.py
│   │   │   │   ├── methods_extract.py
│   │   │   │   ├── claim_classify.py
│   │   │   │   ├── chain_resolve.py
│   │   │   │   ├── elastic_search.py
│   │   │   │   └── protocol_assemble.py
│   │   │   ├── prompts.py           # Loads prompts from docs/PROMPTS.md
│   │   │   └── schemas.py           # Pydantic models for agent I/O
│   │   ├── ingest/
│   │   │   ├── __init__.py
│   │   │   ├── arxiv_client.py
│   │   │   ├── pmc_client.py
│   │   │   ├── openalex_client.py
│   │   │   ├── crossref_client.py
│   │   │   ├── unpaywall_client.py
│   │   │   ├── semantic_scholar_client.py
│   │   │   ├── grobid_client.py
│   │   │   └── pipeline.py          # Orchestrates ingest end to end
│   │   ├── search/
│   │   │   ├── __init__.py
│   │   │   ├── elastic_client.py
│   │   │   ├── indexes.py           # Index definitions
│   │   │   ├── papers_dao.py
│   │   │   ├── claims_dao.py
│   │   │   └── hybrid_search.py
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── firestore_client.py
│   │   │   ├── gcs_client.py
│   │   │   └── redis_client.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── gemini_client.py
│   │   │   └── embeddings.py
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── paper.py
│   │       ├── claim.py
│   │       ├── reconstruction.py
│   │       └── job.py
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── unit/
│       │   ├── test_claim_classify.py
│       │   ├── test_chain_resolve.py
│       │   ├── test_hybrid_search.py
│       │   ├── test_protocol_assemble.py
│       │   └── test_ingest_clients.py
│       ├── integration/
│       │   ├── test_agent_end_to_end.py
│       │   └── test_elastic_indexing.py
│       └── fixtures/
│           ├── papers/              # Sample paper XML/PDFs
│           ├── claims/              # Expected claim extractions
│           └── reconstructions/     # Expected outputs
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.js
│   ├── Dockerfile
│   ├── public/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx                  # Landing + input
│   │   │   ├── globals.css
│   │   │   ├── reconstruct/
│   │   │   │   └── [jobId]/
│   │   │   │       └── page.tsx          # Live progress + final view
│   │   │   └── api/
│   │   │       └── proxy/
│   │   │           └── [...path]/
│   │   │               └── route.ts      # Proxies to backend
│   │   ├── components/
│   │   │   ├── ui/                       # shadcn/ui primitives
│   │   │   ├── paper-input.tsx
│   │   │   ├── agent-stream.tsx          # SSE consumer
│   │   │   ├── protocol-view.tsx
│   │   │   ├── claim-card.tsx
│   │   │   ├── provenance-popover.tsx
│   │   │   ├── gap-report.tsx
│   │   │   ├── score-breakdown.tsx
│   │   │   └── chain-trace.tsx
│   │   ├── lib/
│   │   │   ├── api.ts                    # Backend client
│   │   │   ├── sse.ts                    # SSE helper
│   │   │   ├── types.ts                  # Shared types (mirror backend)
│   │   │   └── utils.ts
│   │   └── hooks/
│   │       └── use-reconstruction.ts
│   └── __tests__/
├── infra/
│   ├── terraform/                        # Optional, IaC for GCP
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── modules/
│   ├── elastic/
│   │   ├── papers_index.json             # Mapping for papers index
│   │   ├── claims_index.json             # Mapping for claims index
│   │   └── pipelines/                    # Ingest pipelines
│   ├── cloudbuild/
│   │   ├── backend.cloudbuild.yaml
│   │   └── frontend.cloudbuild.yaml
│   └── scripts/
│       ├── bootstrap_gcp.sh
│       ├── create_elastic_indexes.py
│       ├── seed_demo_corpus.py
│       └── teardown.sh
├── eval/
│   ├── eval_set.json                     # Held-out test set
│   ├── run_eval.py
│   ├── metrics.py
│   └── reports/
└── .github/
    └── workflows/
        ├── ci.yml                        # Lint, test on PR
        └── deploy.yml                    # Deploy on main
```

---

## 5. Environment Variables (.env.example)

```bash
# Google Cloud
GCP_PROJECT_ID=
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
VERTEX_AI_LOCATION=us-central1
GEMINI_MODEL_PRO=gemini-2.5-pro
GEMINI_MODEL_FLASH=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=text-embedding-005

# Elastic Cloud
ELASTIC_CLOUD_ID=
ELASTIC_API_KEY=
ELASTIC_PAPERS_INDEX=papers
ELASTIC_CLAIMS_INDEX=claims

# Firestore
FIRESTORE_DATABASE=(default)
FIRESTORE_COLLECTION_JOBS=jobs
FIRESTORE_COLLECTION_RECONSTRUCTIONS=reconstructions

# Cloud Storage
GCS_BUCKET_UPLOADS=methods-reconstructor-uploads
GCS_BUCKET_EXPORTS=methods-reconstructor-exports

# Redis (optional for MVP)
REDIS_HOST=localhost
REDIS_PORT=6379

# External APIs (keys where required)
OPENALEX_EMAIL=               # required by polite pool
SEMANTIC_SCHOLAR_API_KEY=     # optional, increases rate limit
UNPAYWALL_EMAIL=              # required
GROBID_URL=http://localhost:8070

# App
APP_ENV=development           # development | staging | production
APP_LOG_LEVEL=INFO
APP_CORS_ORIGINS=http://localhost:3000
APP_MAX_RECURSION_DEPTH=5
APP_PER_PAPER_TOKEN_BUDGET=500000
APP_AGENT_TIMEOUT_SECONDS=300

# Frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SSE_URL=http://localhost:8000
```

---

## 6. External APIs and How We Use Them

### 6.1 OpenAlex — primary paper metadata + citation graph
- Base URL: `https://api.openalex.org`
- No API key required, but set `mailto=` (the polite pool) → use `OPENALEX_EMAIL`
- Endpoints: `/works/{doi}`, `/works?filter=...`
- We use: paper metadata, reference resolution (DOI → DOI graph), open-access status
- Rate limit: 100,000/day with email; we add a 10ms throttle in client

### 6.2 arXiv — primary source for CS/physics/quantitative biology preprints
- Base URL: `http://export.arxiv.org/api/query`
- Use the `arxiv` Python library
- We fetch: abstract + PDF URL; for full text we go to `https://arxiv.org/abs/{id}` then `/pdf/{id}` then optionally GROBID

### 6.3 PubMed Central — full text XML for biomedical papers
- Base URL: `https://www.ncbi.nlm.nih.gov/pmc/`
- E-utilities: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
- Endpoint: `efetch.fcgi?db=pmc&id={pmcid}&rettype=xml`
- This is gold — clean XML with structured methods sections; prefer when available

### 6.4 Crossref — DOI metadata fallback
- Base URL: `https://api.crossref.org`
- Use the `crossrefapi` Python library
- Used when OpenAlex doesn't have a paper

### 6.5 Unpaywall — open-access PDF discovery
- Base URL: `https://api.unpaywall.org/v2`
- Requires `email` parameter → `UNPAYWALL_EMAIL`
- Returns OA URL for a DOI if one exists; we use to bypass paywalls

### 6.6 Semantic Scholar — secondary metadata + references when others fail
- Base URL: `https://api.semanticscholar.org/graph/v1`
- Optional API key in header `x-api-key`
- We use as final fallback for reference resolution

### 6.7 GROBID — PDF → TEI XML extraction
- We host as a sidecar Docker container
- Endpoint: `POST /api/processFulltextDocument`
- Returns TEI XML; we parse with lxml
- Only used when no clean XML is available (i.e., paywalled-but-OA-via-Unpaywall, or PDF upload)

### 6.8 Vertex AI Gemini
- Use `google-genai` SDK (the new one, not `google-generativeai`)
- Models: `gemini-2.5-pro` (planning, decomposition, assembly), `gemini-2.5-flash` (per-claim classification)
- Embeddings: `text-embedding-005` for sentence-level vectors

---

## 7. Data Models (Pydantic + Elastic Mappings)

### 7.1 Pydantic Models — `backend/app/models/`

```python
# paper.py
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class PaperSource(str, Enum):
    ARXIV = "arxiv"
    PMC = "pmc"
    OPENALEX = "openalex"
    CROSSREF = "crossref"
    UPLOAD = "upload"

class Author(BaseModel):
    name: str
    orcid: Optional[str] = None
    affiliation: Optional[str] = None

class Reference(BaseModel):
    ref_id: str              # local id like "ref_1"
    raw_citation: str
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pmc_id: Optional[str] = None
    title: Optional[str] = None
    year: Optional[int] = None
    resolved: bool = False

class Section(BaseModel):
    name: str                # "abstract" | "introduction" | "methods" | ...
    text: str
    sentence_offsets: list[tuple[int, int]] = Field(default_factory=list)

class Paper(BaseModel):
    paper_id: str            # canonical (prefer DOI: "doi:10.xxxx/yyyy")
    source: PaperSource
    title: str
    authors: list[Author]
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    sections: dict[str, Section] = Field(default_factory=dict)
    references: list[Reference] = Field(default_factory=list)
    open_access_url: Optional[str] = None
    full_text_available: bool = False
    ingested_at: str         # ISO timestamp
```

```python
# claim.py
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field

class ClaimType(str, Enum):
    REAGENT = "reagent"
    EQUIPMENT = "equipment"
    SAMPLE_PREP = "sample_prep"
    PROCEDURE = "procedure"
    ANALYSIS = "analysis"
    PARAMETER = "parameter"
    DATASET = "dataset"
    SOFTWARE = "software"

class Specificity(str, Enum):
    FULLY_DESCRIBED = "fully_described"
    PARTIALLY_DESCRIBED = "partially_described"
    SHORTCUT_CITATION = "shortcut_citation"
    STANDARD_UNSPECIFIED = "standard_unspecified"

class ResolutionStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    TERMINAL_GAP = "terminal_gap"

class GapReason(str, Enum):
    DEPTH_EXCEEDED = "depth_exceeded"
    PAYWALL_OR_DEAD = "paywall_or_dead"
    NO_MATCH_IN_CITED = "no_match_in_cited"
    NO_REFERENCE = "no_reference"
    PARSING_FAILED = "parsing_failed"

class ChainStep(BaseModel):
    depth: int
    source_paper_id: str
    sentence_ids: list[int] = Field(default_factory=list)
    extracted_text: str

class Claim(BaseModel):
    claim_id: str            # uuid4
    paper_id: str
    type: ClaimType
    raw_text: str
    raw_sentence_id: int     # sentence in source paper's methods
    specificity: Specificity
    cited_ref_ids: list[str] = Field(default_factory=list)
    resolution_status: ResolutionStatus
    resolved_text: Optional[str] = None
    resolution_chain: list[ChainStep] = Field(default_factory=list)
    terminal_gap_reason: Optional[GapReason] = None
    confidence: float = 0.0  # 0..1
```

```python
# reconstruction.py
from typing import Optional
from pydantic import BaseModel, Field

class SectionScore(BaseModel):
    section: str
    score: float
    n_claims: int
    n_resolved: int

class Gap(BaseModel):
    claim_id: str
    raw_text: str
    reason: str
    chain_trace: list[dict]
    suggested_action: str

class ReconstructedProtocol(BaseModel):
    protocol_id: str
    job_id: str
    source_paper_id: str
    title: str
    reproducibility_score: float
    section_scores: list[SectionScore]
    sections: dict[str, list[Claim]]  # keyed by claim type
    gaps: list[Gap]
    generated_at: str
    version: str = "1.0.0"
```

```python
# job.py
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class JobStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    DECOMPOSING = "decomposing"
    RESOLVING = "resolving"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    FAILED = "failed"

class JobEvent(BaseModel):
    timestamp: str
    status: JobStatus
    message: str
    detail: Optional[dict] = None

class Job(BaseModel):
    job_id: str
    paper_input: str         # raw input from user
    status: JobStatus
    events: list[JobEvent] = Field(default_factory=list)
    paper_id: Optional[str] = None
    protocol_id: Optional[str] = None
    error: Optional[str] = None
    started_at: str
    updated_at: str
    completed_at: Optional[str] = None
```

### 7.2 Elastic Mappings — `infra/elastic/papers_index.json`

```json
{
  "mappings": {
    "properties": {
      "paper_id": {"type": "keyword"},
      "source": {"type": "keyword"},
      "title": {"type": "text", "analyzer": "english"},
      "authors": {
        "type": "nested",
        "properties": {
          "name": {"type": "text"},
          "orcid": {"type": "keyword"}
        }
      },
      "year": {"type": "integer"},
      "venue": {"type": "keyword"},
      "abstract": {"type": "text", "analyzer": "english"},
      "abstract_vector": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine"
      },
      "methods_text": {"type": "text", "analyzer": "english"},
      "methods_sentences": {
        "type": "nested",
        "properties": {
          "sentence_id": {"type": "integer"},
          "text": {"type": "text", "analyzer": "english"},
          "vector": {
            "type": "dense_vector",
            "dims": 768,
            "index": true,
            "similarity": "cosine"
          }
        }
      },
      "references": {
        "type": "nested",
        "properties": {
          "ref_id": {"type": "keyword"},
          "doi": {"type": "keyword"},
          "arxiv_id": {"type": "keyword"},
          "pmc_id": {"type": "keyword"},
          "raw_citation": {"type": "text"},
          "resolved": {"type": "boolean"}
        }
      },
      "open_access_url": {"type": "keyword"},
      "ingested_at": {"type": "date"}
    }
  }
}
```

### 7.3 Elastic Mappings — `infra/elastic/claims_index.json`

```json
{
  "mappings": {
    "properties": {
      "claim_id": {"type": "keyword"},
      "paper_id": {"type": "keyword"},
      "type": {"type": "keyword"},
      "raw_text": {"type": "text", "analyzer": "english"},
      "raw_sentence_id": {"type": "integer"},
      "specificity": {"type": "keyword"},
      "cited_ref_ids": {"type": "keyword"},
      "resolution_status": {"type": "keyword"},
      "resolved_text": {"type": "text", "analyzer": "english"},
      "resolution_chain": {
        "type": "nested",
        "properties": {
          "depth": {"type": "integer"},
          "source_paper_id": {"type": "keyword"},
          "sentence_ids": {"type": "integer"},
          "extracted_text": {"type": "text"}
        }
      },
      "terminal_gap_reason": {"type": "keyword"},
      "confidence": {"type": "float"},
      "embedding": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
```

---

## 8. Agent Architecture (The Core IP)

### 8.1 Agent Loop — Pseudocode (authoritative)

```
ENTRY: run_reconstruction(paper_input: str) -> ReconstructedProtocol

1. INGEST
   paper = ingest_pipeline(paper_input)
     a. Resolve identifier (arxiv id | doi | pmc id | URL)
     b. Fetch metadata via OpenAlex / arXiv / PMC / Crossref
     c. Fetch full text:
          - Prefer PMC XML > arXiv abstract+PDF > Crossref+Unpaywall+GROBID
     d. Parse references; for each, attempt to resolve to canonical id
     e. Index paper into Elastic papers index with sentence-level vectors
     emit_event(INGESTING_DONE, {paper_id})

2. DECOMPOSE
   claims = methods_extract.extract(paper)
     a. Gemini Pro reads methods section
     b. Returns structured list of Claim objects (specificity classified)
     c. Index all claims into Elastic claims index
     emit_event(DECOMPOSING_DONE, {n_claims})

3. RESOLVE (the recursive loop)
   FOR claim IN claims WHERE specificity != FULLY_DESCRIBED:
     resolution = resolve_claim(claim, depth=0)
     update claim with resolution_status, resolution_chain, etc.
     re-index updated claim
     emit_event(CLAIM_RESOLVED, {claim_id, status})

4. ASSEMBLE
   protocol = protocol_assemble.assemble(paper, claims)
     a. Gemini Pro takes all claims (resolved + gaps)
     b. Synthesizes structured Reconstructed Protocol
     c. Computes section scores + overall reproducibility score
     d. Generates gap report with suggested actions
   store protocol in Firestore + GCS
   emit_event(COMPLETE, {protocol_id})

5. RETURN protocol


SUBROUTINE: resolve_claim(claim, depth) -> resolution_result
  IF depth > MAX_RECURSION_DEPTH:
    return TerminalGap(DEPTH_EXCEEDED)

  IF claim.specificity == SHORTCUT_CITATION:
    IF claim.cited_ref_ids is empty:
      return TerminalGap(NO_REFERENCE)

    FOR ref_id IN claim.cited_ref_ids:
      ref_paper = paper_fetch.fetch_by_ref(ref_id)
      IF ref_paper is None:
        continue
      IF ref_paper not in elastic:
        index ref_paper into elastic
      relevant_passage = methods_locator.find(ref_paper, claim)
      IF relevant_passage.fully_describes:
        return Resolved(passage)
      ELIF relevant_passage.is_itself_shortcut:
        sub_claim = build_subclaim_for_passage(passage)
        return resolve_claim(sub_claim, depth + 1)
      ELSE:
        continue

    return TerminalGap(NO_MATCH_IN_CITED)

  IF claim.specificity == PARTIALLY_DESCRIBED:
    # Try to augment from the broader corpus
    candidates = elastic_hybrid_search(claim.raw_text, top_k=5)
    augmented = augment_partial_claim(claim, candidates)
    IF augmented.succeeded:
      return Resolved(augmented.text)
    return TerminalGap(NO_MATCH_IN_CITED)

  IF claim.specificity == STANDARD_UNSPECIFIED:
    # "Standard conditions" — search for what "standard" means in this subfield
    candidates = elastic_hybrid_search(claim.raw_text, top_k=10)
    standard_resolution = resolve_standard(claim, candidates)
    IF standard_resolution.succeeded:
      return Resolved(standard_resolution.text, confidence=lower)
    return TerminalGap(NO_MATCH_IN_CITED)


SUBROUTINE: methods_locator.find(ref_paper, claim) -> Passage
  # Given a cited paper and the claim being resolved,
  # find the specific sentences in the cited paper's methods that describe the procedure.
  query_vector = embed(claim.raw_text)
  hits = elastic_nested_knn_search(
    index="papers",
    paper_id=ref_paper.paper_id,
    field="methods_sentences",
    query_vector=query_vector,
    k=10
  )
  passage_text = concatenate(hits)
  classification = gemini_flash_classify_passage(claim, passage_text)
  # returns: {fully_describes: bool, is_itself_shortcut: bool, cited_refs: [...]}
  return Passage(text=passage_text, ...classification)
```

### 8.2 Why this is genuinely agentic

- The agent makes a recursive sequence of decisions, where each decision (what to fetch next, whether the fetched content resolves the claim, whether to recurse) requires reasoning over the previous result.
- The tool graph is dynamic — the agent does not know at the start how many papers it will fetch.
- A vanilla single-shot RAG cannot do this; the citation chain depth is unbounded a priori.

### 8.3 Tool Definitions (MCP-style)

Each tool is a Python function in `backend/app/agent/tools/`. The agent runner invokes them by name.

```python
# Tool: paper_fetch
def paper_fetch(identifier: str) -> Paper | None:
    """
    Resolve an identifier (DOI, arxiv id, pmc id, URL, raw citation)
    to a canonical Paper object. Returns None if unrecoverable.
    """

# Tool: paper_parse
def paper_parse(paper: Paper) -> Paper:
    """
    Ensure paper has sections populated. Calls GROBID if needed.
    """

# Tool: methods_extract
def methods_extract(paper: Paper) -> list[Claim]:
    """
    Given a paper with a methods section, extract structured claims.
    Uses Gemini Pro.
    """

# Tool: claim_classify
def claim_classify(text: str) -> dict:
    """
    Classify the specificity of a single methodological statement.
    Returns {type, specificity, cited_ref_ids}.
    Uses Gemini Flash.
    """

# Tool: elastic_search
def elastic_search(
    query: str,
    index: str = "papers",
    filters: dict | None = None,
    top_k: int = 10,
    hybrid: bool = True
) -> list[dict]:
    """
    Hybrid BM25 + vector search. Returns ranked hits.
    """

# Tool: methods_locator
def methods_locator(ref_paper: Paper, claim: Claim) -> Passage:
    """
    Find the specific sentences in ref_paper's methods that describe
    the procedure referenced by claim. Returns Passage with classification.
    """

# Tool: chain_resolve
def chain_resolve(claim: Claim, depth: int = 0) -> ResolutionResult:
    """
    The recursive resolver. Calls itself for shortcut chains.
    """

# Tool: protocol_assemble
def protocol_assemble(
    paper: Paper,
    claims: list[Claim]
) -> ReconstructedProtocol:
    """
    Synthesize the final Reconstructed Protocol document.
    Uses Gemini Pro.
    """
```

---

## 9. LLM Prompts (Source of Truth)

All prompts live in `docs/PRMPTS.md` (referenced from `backend/app/agent/prompts.py`). Below are the production prompts; copy verbatim.

### 9.1 Methods Decomposition Prompt (Gemini 2.5 Pro)

```
SYSTEM:
You are an expert in scientific methods analysis. Your job is to decompose
a methods section into structured methodological claims.

For each distinct methodological statement, classify:
1. TYPE: one of [reagent, equipment, sample_prep, procedure, analysis, parameter, dataset, software]
2. SPECIFICITY:
   - fully_described: the procedure is described with enough detail to follow it
   - partially_described: some detail present, but key parameters or steps missing
   - shortcut_citation: the procedure is delegated to another paper via phrases like
     "as described in", "following the protocol of", "see [N] for details"
   - standard_unspecified: phrases like "standard conditions", "as is conventional",
     with no further detail
3. CITED_REF_IDS: if a shortcut, the reference ids being delegated to (e.g. ["ref_12", "ref_7"])

CRITICAL RULES:
- Do not invent procedures not stated in the text.
- A claim must correspond to a contiguous span of source text; record the sentence id.
- If a single sentence contains multiple claims, emit multiple Claim objects.
- The presence of a citation does NOT automatically make a claim a shortcut. A shortcut
  is when the citation REPLACES procedural detail, not when it supports a stated fact.

OUTPUT FORMAT:
Return a JSON object with a single key "claims" whose value is an array of objects
with fields: type, specificity, cited_ref_ids, raw_text, raw_sentence_id.

USER:
The following is the methods section of paper {paper_id}, titled "{title}".
Each sentence is prefixed with its sentence id in square brackets.

References available in this paper:
{references_list}

Methods section:
{methods_text_with_sentence_ids}
```

### 9.2 Methods Locator / Passage Classifier (Gemini 2.5 Flash)

```
SYSTEM:
You are checking whether a passage from one scientific paper describes a procedure
that another paper cited it for.

Given:
- ORIGINAL_CLAIM: a methodological claim from the citing paper.
- CANDIDATE_PASSAGE: sentences retrieved from the cited paper's methods section.

Decide:
1. FULLY_DESCRIBES: does the candidate passage contain enough detail to fully describe
   the procedure referenced by the original claim? (true/false)
2. IS_ITSELF_SHORTCUT: does the candidate passage itself shortcut to yet another
   paper for the procedure? (true/false)
3. NEW_CITED_REFS: if it shortcuts, list the new references being delegated to.

OUTPUT FORMAT:
JSON: {"fully_describes": bool, "is_itself_shortcut": bool, "new_cited_refs": [str]}

USER:
ORIGINAL_CLAIM:
{claim_raw_text}

CANDIDATE_PASSAGE (from cited paper {ref_paper_id}):
{passage_text}
```

### 9.3 Protocol Assembly Prompt (Gemini 2.5 Pro)

```
SYSTEM:
You are assembling a reproducible protocol document from a paper plus a set of
resolved and unresolved methodological claims.

Produce a clean, structured protocol with the following sections (omit empty ones):
1. Reagents & Materials
2. Equipment
3. Sample Preparation
4. Procedure (numbered steps)
5. Data Analysis
6. Software & Parameters
7. Datasets

CRITICAL RULES:
- Every assertion in the protocol MUST be traceable to a specific claim_id from the input.
- Do not invent details not present in the claim's resolved_text or raw_text.
- For claims with TERMINAL_GAP, do not include them in the protocol body; they go in
  the gap report instead.
- Preserve the original paper's terminology and units.
- Numbered procedure steps should follow logical execution order, not document order.

OUTPUT FORMAT:
JSON with structure:
{
  "sections": {
    "reagents": [{"claim_id": "...", "text": "..."}],
    "equipment": [...],
    "sample_prep": [...],
    "procedure": [...],
    "analysis": [...],
    "software": [...],
    "datasets": [...]
  },
  "gap_report": [
    {
      "claim_id": "...",
      "raw_text": "...",
      "reason": "...",
      "suggested_action": "..."
    }
  ]
}

USER:
Source paper: {paper_title} ({paper_id})

Claims (JSON):
{claims_json}
```

### 9.4 Reproducibility Scoring (deterministic, not LLM)

The score is computed in Python, not by an LLM, to keep it reproducible and explainable:

```
score = 100 * weighted_sum(resolved) / weighted_sum(all)

weights:
  procedure: 3.0
  sample_prep: 3.0
  analysis: 2.5
  parameter: 2.0
  reagent: 1.5
  equipment: 1.0
  software: 1.5
  dataset: 2.0

a claim contributes (weight * resolution_factor) where:
  resolution_factor = 1.0 if RESOLVED
                    = 0.5 if RESOLVED with confidence < 0.7
                    = 0.0 if TERMINAL_GAP
                    = 0.7 if FULLY_DESCRIBED in original (no resolution needed)
```

---

## 10. API Contracts (Backend Endpoints)

All endpoints are JSON. Errors return `{"error": "...", "detail": "..."}` with appropriate HTTP status.

### POST `/api/papers/ingest`
Ingests a paper without running reconstruction.
- Request: `{"identifier": "arxiv:2301.12345" | "doi:10.xxxx/yyyy" | "pmc:PMC123" | "url"}` or `multipart/form-data` with PDF
- Response: `{"paper_id": "...", "title": "...", "status": "ingested"}`

### POST `/api/reconstructions`
Starts a reconstruction job.
- Request: `{"identifier": "..."}` OR `{"paper_id": "..."}`
- Response: `{"job_id": "...", "stream_url": "/api/reconstructions/{job_id}/stream"}`

### GET `/api/reconstructions/{job_id}`
Polls job status.
- Response: `Job` JSON object

### GET `/api/reconstructions/{job_id}/stream` (SSE)
Streams live agent events.
- Event types: `ingest`, `decompose`, `claim_resolved`, `claim_failed`, `assemble`, `complete`, `error`
- Each event: `{"type": "...", "timestamp": "...", "data": {...}}`

### GET `/api/reconstructions/{job_id}/protocol`
Returns the final reconstructed protocol.
- Response: `ReconstructedProtocol` JSON

### GET `/api/reconstructions/{job_id}/export.{format}`
Exports the protocol in the given format.
- formats: `json`, `pdf`, `md`, `csv` (gap report only)
- Response: file download

### GET `/api/health`
Liveness check.
- Response: `{"status": "ok", "version": "..."}`

---

## 11. Frontend Specification

### 11.1 Screens

**Landing / Input Screen (`/`)**
- Hero with the product name and one-line value prop
- Single input field accepting: DOI, arXiv URL, arXiv ID, PMC ID, or PDF upload
- Three example papers as one-click demo buttons
- "Recently reconstructed" carousel (cached examples)

**Reconstruction Screen (`/reconstruct/[jobId]`)**

Three states based on job status:

1. **In progress** — left panel shows live agent stream (each event as a card with timestamp, status, message). Right panel shows the reconstruction skeleton filling in section by section.

2. **Complete** — full protocol view with:
   - Header: paper title, authors, reproducibility score (large), section scores (small bars)
   - Tabs: Protocol | Gap Report | Provenance Graph
   - Protocol tab: structured sections, each claim is a card with hover-to-show provenance (chain trace, source paper, exact sentences)
   - Gap report tab: list of unresolved items, each with reason and suggested action
   - Provenance graph tab: interactive citation chain visualization (use react-flow or similar)
   - Export menu: PDF, Markdown, JSON, CSV

3. **Error** — clear error message with retry button

### 11.2 Component Spec

Each component in `frontend/src/components/` must:
- Be a React Server Component by default; client components only when needed (state, events)
- Use `cn()` (clsx + tailwind-merge) for class composition
- Be typed with TypeScript strict mode
- Have a Storybook entry (`*.stories.tsx`) — stretch goal

### 11.3 SSE Consumer (`agent-stream.tsx`)

```tsx
"use client";
import { useEffect, useState } from "react";

type AgentEvent = {
  type: string;
  timestamp: string;
  data: Record<string, unknown>;
};

export function AgentStream({ jobId }: { jobId: string }) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const url = `${process.env.NEXT_PUBLIC_SSE_URL}/api/reconstructions/${jobId}/stream`;
    const es = new EventSource(url);
    es.onmessage = (e) => {
      const ev: AgentEvent = JSON.parse(e.data);
      setEvents((prev) => [...prev, ev]);
      if (ev.type === "complete" || ev.type === "error") {
        setDone(true);
        es.close();
      }
    };
    es.onerror = () => { es.close(); setDone(true); };
    return () => es.close();
  }, [jobId]);

  return (
    <div className="space-y-2">
      {events.map((ev, i) => (
        <EventCard key={i} event={ev} />
      ))}
    </div>
  );
}
```

---

## 12. Infrastructure

### 12.1 Local Dev — `docker-compose.yml`

```yaml
services:
  grobid:
    image: lfoppiano/grobid:0.8.1
    ports:
      - "8070:8070"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8070/api/isalive"]
      interval: 30s

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    env_file: ./.env
    ports:
      - "8000:8000"
    depends_on:
      - grobid
      - redis
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

  frontend:
    build: ./frontend
    env_file: ./.env
    ports:
      - "3000:3000"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm run dev
```

### 12.2 GCP Bootstrap — `infra/scripts/bootstrap_gcp.sh`

Idempotent script that:
1. Sets the project, enables required APIs (Vertex AI, Cloud Run, Firestore, Cloud Storage, Secret Manager, Artifact Registry)
2. Creates a service account with required roles
3. Creates Cloud Storage buckets
4. Creates the Firestore database in Native mode
5. Outputs the env vars to populate `.env`

### 12.3 Elastic Setup — `infra/scripts/create_elastic_indexes.py`

```python
from elasticsearch import Elasticsearch
import json, os

es = Elasticsearch(cloud_id=os.environ["ELASTIC_CLOUD_ID"],
                   api_key=os.environ["ELASTIC_API_KEY"])

for name, path in [("papers", "infra/elastic/papers_index.json"),
                   ("claims", "infra/elastic/claims_index.json")]:
    with open(path) as f:
        mapping = json.load(f)
    if not es.indices.exists(index=name):
        es.indices.create(index=name, body=mapping)
        print(f"Created index: {name}")
    else:
        print(f"Index already exists: {name}")
```

### 12.4 Deployment — Cloud Build

`infra/cloudbuild/backend.cloudbuild.yaml` builds and deploys the FastAPI image to Cloud Run. Same pattern for frontend.

---

## 13. Testing

### 13.1 Test Commands

```bash
make test            # runs all
make test-unit       # backend unit tests
make test-integration # backend integration (requires .env)
make test-frontend   # frontend tests
make lint            # ruff + mypy + eslint
make eval            # run eval harness against eval_set.json
```

### 13.2 Critical Tests to Write

**Unit (backend/tests/unit/)**

- `test_claim_classify.py` — given known sentences, classify specificity correctly (≥90% on a held-out set of 30 sentences in fixtures)
- `test_chain_resolve.py` — mock paper_fetch; verify recursion respects depth cap, terminates on dead ends, terminates on resolution
- `test_hybrid_search.py` — index 5 known papers, query, verify ranking
- `test_protocol_assemble.py` — given mock claims, verify protocol JSON shape and that no claim is invented
- `test_ingest_clients.py` — each external API client (arxiv, pmc, openalex, etc.) handles success, 404, and rate-limit cases

**Integration (backend/tests/integration/)**

- `test_agent_end_to_end.py` — runs the full agent on one known paper from fixtures, asserts the final protocol has expected structure
- `test_elastic_indexing.py` — round-trip a paper through ingest → index → query

### 13.3 Eval Set

`eval/eval_set.json` contains 10 hand-picked papers with manually-annotated expected outputs:
- Number of claims by type
- Number of shortcut citations
- For 3 selected claims per paper, the expected resolution chain
- Expected reproducibility score range

`eval/run_eval.py` runs the agent against each and computes:
- Claim recall and classification accuracy
- Resolution success rate
- Score correlation with manual rating

---

## 14. Build Order (Follow Strictly)

Each task ends with a commit, a test pass, and confirmation from the human before starting the next.

**Task 1 — Repo skeleton**
- Create the full directory structure from Section 4
- Add `.gitignore`, `LICENSE` (Apache 2.0), `README.md` with project intro
- Add `.env.example`
- Add `Makefile` targets (initially stubs)
- Initial commit
- **Stop. Confirm.**

**Task 2 — Backend bootstrap**
- `backend/pyproject.toml` with dependencies from Section 3
- `backend/app/main.py` minimal FastAPI app with `/api/health`
- `backend/app/config.py` with pydantic Settings
- `backend/app/logging.py`
- `backend/Dockerfile`
- One unit test that hits `/api/health`
- `make test-unit` passes
- **Stop. Confirm.**

**Task 3 — Frontend bootstrap**
- `frontend/package.json` with deps from Section 3
- Next.js 14 App Router scaffold
- shadcn/ui init + Tailwind config
- Landing page with input field (no functionality yet) and three example buttons
- `frontend/Dockerfile`
- `docker-compose.yml` brings up backend + frontend + grobid + redis
- **Stop. Confirm.**

**Task 4 — Elastic + Firestore + GCS clients**
- `backend/app/search/elastic_client.py` connection helper
- `backend/app/storage/firestore_client.py`
- `backend/app/storage/gcs_client.py`
- `infra/elastic/papers_index.json` and `claims_index.json`
- `infra/scripts/create_elastic_indexes.py`
- Smoke test: create indexes, write a doc, read it back, delete
- **Stop. Confirm.**

**Task 5 — Ingest clients**
- Implement each client in `backend/app/ingest/` per Section 6
- Each with its own unit tests using mocked HTTP
- `pipeline.py` orchestrates: identifier → metadata → full text → references → indexed Paper
- Test on 3 known papers (one arXiv, one PMC, one DOI-only)
- **Stop. Confirm.**

**Task 6 — Embeddings + sentence indexing**
- `backend/app/llm/embeddings.py` — wraps Vertex AI text-embedding-005
- Modify ingest pipeline to chunk methods into sentences and embed each
- Verify nested kNN search works
- **Stop. Confirm.**

**Task 7 — Methods decomposition tool**
- `backend/app/agent/tools/methods_extract.py` using Gemini Pro
- Prompt from Section 9.1
- Unit test against fixtures
- **Stop. Confirm.**

**Task 8 — Hybrid search + methods locator**
- `backend/app/search/hybrid_search.py` — BM25 + dense vector with RRF fusion
- `methods_locator` function that finds sentences in a cited paper matching a claim
- Passage classifier with prompt from Section 9.2
- **Stop. Confirm.**

**Task 9 — Chain resolver (the core IP)**
- `backend/app/agent/tools/chain_resolve.py` implementing the recursive loop
- Hard depth cap from `APP_MAX_RECURSION_DEPTH`
- Comprehensive unit tests with mocked sub-tools
- **Stop. Confirm.**

**Task 10 — Protocol assembler**
- `backend/app/agent/tools/protocol_assemble.py` using Gemini Pro
- Prompt from Section 9.3
- Deterministic reproducibility score from Section 9.4
- **Stop. Confirm.**

**Task 11 — Agent runner + API endpoints**
- `backend/app/agent/runner.py` orchestrates the full loop
- API routes from Section 10
- SSE event streaming via sse-starlette
- Job state persisted in Firestore
- Integration test: full agent run on one fixture paper
- **Stop. Confirm.**

**Task 12 — Frontend reconstruction screen**
- `frontend/src/app/reconstruct/[jobId]/page.tsx`
- `AgentStream` SSE consumer
- `ProtocolView`, `ClaimCard`, `ProvenancePopover`, `GapReport`, `ScoreBreakdown`
- End-to-end test: paste URL on landing → navigate to reconstruct → see live stream → see final protocol
- **Stop. Confirm.**

**Task 13 — Exports**
- `routes_exports.py` with JSON, Markdown, PDF (use weasyprint or reportlab), CSV
- Export buttons in frontend
- **Stop. Confirm.**

**Task 14 — Eval harness**
- `eval/eval_set.json` with 10 papers
- `eval/run_eval.py` produces metrics
- Run, record baseline scores
- **Stop. Confirm.**

**Task 15 — Demo polish**
- Pre-cache 3-5 demo papers so the demo is fast and deterministic
- Add example buttons on landing tied to those papers
- Add a "what is this?" modal explaining the product
- Add loading skeletons and empty states
- Polish typography, spacing, color
- **Stop. Confirm.**

**Task 16 — Deployment**
- Deploy backend to Cloud Run via Cloud Build
- Deploy frontend to Cloud Run via Cloud Build
- Wire up custom domain (if available)
- Smoke test live URL
- **Stop. Confirm.**

**Task 17 — Submission artifacts**
- Record demo video per `docs/DEMO_SCRIPT.md`
- Write `README.md` final version with setup instructions
- Ensure repo is public with Apache 2.0 license visible
- Submit on Devpost per hackathon rules
- **Stop. Confirm.**

---

## 15. Things Claude Code Must NOT Do

- Do NOT add features not in this spec without asking.
- Do NOT pick alternative libraries when one is pinned (no swapping FastAPI for Flask, no swapping Next.js for Vite).
- Do NOT use `localStorage` or `sessionStorage` anywhere; use Firestore for persistence, React state for UI.
- Do NOT call Gemini directly from the frontend; all LLM calls go through the backend.
- Do NOT commit `.env`, credentials, or any secrets.
- Do NOT hardcode paper content into the codebase; everything flows through the ingest pipeline.
- Do NOT skip tests to move faster. Tests are part of the deliverable.
- Do NOT generate copyrighted text in any output (the protocol assembler must reword and cite, not copy paragraphs).
- Do NOT call `npm install -g` or `pip install` outside the project's dependency manifests.
- Do NOT add UI elements that imply functionality that isn't implemented yet.

---

## 16. Things Claude Code SHOULD Do

- DO check off each Build Order task only after its test commands pass.
- DO write a one-paragraph progress summary at the end of each task.
- DO ask the human if you find ambiguity in the spec rather than guessing.
- DO flag if you find that a pinned library version doesn't work and propose an alternative for human approval.
- DO commit with conventional commit messages: `feat(agent): add chain resolver`, `test(ingest): cover arxiv 404 path`, etc.
- DO keep functions under 50 lines where reasonable; refactor when they grow.
- DO add docstrings to every public function.
- DO log structured events at INFO level for all agent steps so we can debug.
- DO use `tenacity` for retries on external API calls with exponential backoff.

---

## 17. Glossary

- **Shortcut citation** — a citation that replaces methodological detail (e.g., "as in Smith 2019"); the central problem this product solves.
- **Citation chain** — sequence of shortcut citations forming a dependency graph; can dead-end.
- **Terminal gap** — a claim that could not be resolved; surfaced in the gap report.
- **Reproducibility score** — 0–100 metric of how self-contained a paper's methods are.
- **Provenance** — the trace from a claim in the reconstructed protocol back to the source sentences.
- **Hybrid search** — BM25 + dense vector retrieval combined via reciprocal rank fusion.
- **MAR** — Monthly Active Rows, not relevant here but Fivetran-track terminology.
- **MCP** — Model Context Protocol, the interface Anthropic defined for tools; we use the *concept* (tool-call abstraction) even though the agent runs via ADK.

---

## 18. Open Questions for the Human

These need answers before or during early build:

1. **Domain focus for demo papers** — biology, chemistry, ML, or mixed?
2. **Auth** — single-user demo or multi-user with Google sign-in?
3. **Custom domain** — do we own one for the deployed demo, or use the default Cloud Run URL?
4. **Branding** — is "Methods Reconstructor" the final name? Logo?
5. **Team** — solo build or with collaborators registered as a hackathon team (max 4)?

---

End of spec.
