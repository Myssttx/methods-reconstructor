# PRD: Methods Reconstructor

**An agent that turns shortcut-citation-riddled methods sections into self-contained, reproducible protocols — and flags exactly where the chain breaks.**

*Hackathon: Google Cloud Rapid Agent Hackathon — Elastic Track*

---

## 1. Problem Statement

Scientific methods sections frequently fail their core purpose. They are riddled with **methodological shortcut citations** — phrases like *"as described previously,"* *"following the protocol of Smith et al. 2019,"* or *"under standard conditions"* — that delegate the actual procedural detail to other papers. Those citations form chains that often dead-end at:

- Papers behind paywalls the reader can't access
- Papers that themselves use shortcut citations to yet other papers (recursive failure)
- Supplementary materials no longer hosted
- "Standard protocols" that are only standard in the originating lab
- Dead URLs, defunct repositories, missing GitHub repos

**The downstream impact is measured and severe.** The Reproducibility Project: Cancer Biology attempted to replicate 193 high-profile cancer papers; *zero* contained sufficient methodological detail to design a replication study. When original authors were contacted to fill gaps, 32% did not respond or were unhelpful. The 2016 Nature survey of 1,576 researchers found that 70%+ had failed to reproduce another scientist's experiment, with incomplete protocol detail cited as the most common cause.

Existing solutions (protocols.io, PRISMA-style reporting checklists, journal mandates) operate on the **author side** and require voluntary participation going forward. They do nothing for:

- The tens of millions of existing papers
- Authors who don't deposit detailed protocols
- The reader who is trying *right now* to reproduce a specific result

## 2. Product Vision

**Methods Reconstructor** is a consumer-side agent. Anyone trying to understand, teach, replicate, or extend a paper can feed it the paper and receive back a fully assembled methods document — one that resolves every shortcut citation it can, surfaces explicit prose for every parameter and procedural step, and provides a structured gap report listing exactly what could not be recovered and why.

The agent does not replace human judgment. It does the mechanical, time-consuming, recursive work of citation chasing, methods extraction, and gap identification — work that currently consumes weeks of a researcher's time and frequently ends in defeat.

## 3. Target Users

**Primary**
1. **Graduate students attempting to replicate or extend a published method.** Highest pain, highest time savings, most enthusiastic adopters.
2. **Postdocs and PIs onboarding new lab members** who need to learn techniques from the literature without weeks of citation-chasing.

**Secondary**
3. **Systematic reviewers and meta-analysts** doing PRISMA-style work where methods quality assessment is a core deliverable.
4. **Peer reviewers** wanting to spot-check whether a methods section is genuinely self-contained or contains unverified shortcut chains.
5. **Journal editors and integrity officers** evaluating methodological transparency across a corpus.

## 4. User Stories

- *As a grad student, I paste a paper URL and within ~2 minutes get a self-contained methods document I can actually follow, plus a list of the 4 things the agent couldn't recover so I know exactly what to email the corresponding author about.*
- *As a postdoc, I upload a PDF of an old paper and the agent traces every "as described in" backward, returns the resolved procedure, and tells me which of three cited papers is the actually-authoritative source.*
- *As a systematic reviewer, I batch-process 50 papers and export a CSV showing methodological completeness scores per paper and per dimension (reagents, statistical analysis, sample prep, etc.).*
- *As a peer reviewer, I drop in a manuscript and immediately see which methodological claims are unsupported, which cite paywalled papers, and which point to broken URLs.*

## 5. Differentiation

| Approach | What it does | Why it doesn't solve the problem |
|---|---|---|
| protocols.io | Deposit a detailed protocol with a DOI | Voluntary; ~33% of researchers participate; doesn't help with existing papers |
| Reporting checklists (PRISMA, ARRIVE) | Author confirms a section exists | Doesn't verify the section is self-contained |
| Google Scholar, Semantic Scholar | Search papers by topic | Returns papers, not resolved procedures |
| Generic RAG-over-papers chatbots | Q&A over a corpus | Single-hop retrieval; doesn't recursively resolve citation chains; doesn't structure output as a reproducible protocol |
| **Methods Reconstructor** | **Recursive citation resolution + methods extraction + gap reporting** | — |

The defensible angle is the **recursive agentic loop** specifically tuned for methodological dependency graphs, plus a **structured output format** (a reproducibility-ready protocol document) that no generic tool produces.

## 6. Core Features (MVP)

### F1. Paper Ingest
- Accept input as: arXiv ID, DOI, PubMed ID, PDF upload, or URL to a hosted paper.
- Resolve to canonical paper record. Pull metadata (title, authors, year, venue, abstract).
- Extract full text with section structure preserved (Introduction, Methods, Results, etc.).
- Index the full paper into Elastic.

### F2. Methods Decomposition
The agent reads the Methods section and decomposes it into structured **methodological claims**, each labeled with:
- **Type**: reagent, instrument/equipment, sample preparation step, experimental procedure, statistical analysis, software/tool, dataset, parameter setting.
- **Specificity score**: fully described | partially described | shortcut citation | "standard" / unspecified.
- **Resolution status** (initially): unresolved if a shortcut.

### F3. Citation Chain Resolution (the core agentic loop)
For each unresolved methodological claim:
1. Extract the cited reference(s).
2. Fetch the cited paper (Elastic corpus → external APIs if needed).
3. Search the cited paper's methods for the specific procedure being borrowed.
4. If the cited paper contains a full description → resolved.
5. If the cited paper itself uses a shortcut citation → recurse (with a depth cap, default 5).
6. If the cited paper is inaccessible / broken / paywalled / removed → terminal gap.
7. If recursion exceeds depth cap → terminal gap with chain trace.

### F4. Protocol Assembly
Produce a single, structured **Reconstructed Protocol** document with:
- **Reagents & Materials** (with CAS numbers, vendor catalog numbers, concentrations where recoverable)
- **Equipment** (models, settings)
- **Step-by-step procedure** (numbered, with timing and parameters)
- **Data analysis** (statistical tests, software versions, parameter values, code links)
- **Inline provenance**: every resolved claim is linked to the source paper and the specific sentence(s) it was extracted from
- A **confidence score** per section

### F5. Gap Report
A structured report of everything the agent *could not* recover:
- Specific procedural detail missing
- Why (paywall / dead URL / shortcut depth exceeded / cited paper itself shortcuts / no methods detail in cited paper)
- Suggested next action (which author to contact, which database to check manually, which alternative paper might contain the missing detail)

### F6. Reproducibility Score
A per-paper score (0-100) derived from the proportion of methodological claims fully resolved, weighted by claim type. Critical claims (sample prep, statistical analysis) weighted higher than peripheral claims (general equipment).

### F7. Interactive Drill-Down
The user can click any claim in the reconstructed protocol to see:
- The original sentence from the source paper
- The full citation chain that led to resolution
- Confidence rationale

### F8. Export
- PDF of reconstructed protocol
- Markdown for protocols.io upload
- JSON for programmatic use
- CSV gap report for batch processing

## 7. Out-of-Scope for MVP

- Actually executing protocols or generating code
- Authoring new papers
- Critiquing scientific validity (the agent reconstructs what *is* described; it doesn't judge whether the design is good)
- Multimodal extraction from figures and gels (text-only for v1)
- Languages other than English
- A full author-side deposit workflow (we're consumer-side)

## 8. Success Metrics

**For the hackathon demo**
- End-to-end runtime under 3 minutes for a representative paper
- Resolves ≥70% of shortcut citations on a held-out test set of 10 papers
- Gap report flags every known irrecoverable item (validated against manual baseline)
- Reproducibility scores correlate with independent expert ratings

**For a real product**
- Time-to-protocol reduction (target: weeks → minutes)
- Adoption by at least one metascience research group within 6 months
- Coverage breadth (target: usable across biology, chemistry, ML/CS, materials science)

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Paywalled papers block citation resolution | Use open-access first (arXiv, bioRxiv, PMC, OpenAlex); transparently flag paywall gaps |
| Hallucinated procedural detail | Every claim must cite the exact source sentence; no synthesis without provenance; tune the prompt for "say I don't know" |
| Citation chains too deep / too costly | Hard depth cap (5); per-paper token budget; cache aggressively |
| Methods extraction quality varies by field | Demo on biology + chemistry where the problem is best-documented; note generalization to other fields as future work |
| Misuse for "research without reading" | Position as augmentation, not replacement; provenance everywhere; the gap report makes clear what's still missing |

---

## 10. Full-Stack Architecture

### 10.1 System Topology

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js, hosted on Cloud Run)                         │
│  - Paper input, reconstructed protocol view, gap report viewer   │
└──────────────┬───────────────────────────────────────────────────┘
               │ HTTPS
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  API Layer (FastAPI on Cloud Run)                                │
│  - Auth, job orchestration, SSE for live progress                │
└──────┬───────────┬────────────┬─────────────────────────┬────────┘
       │           │            │                         │
       ▼           ▼            ▼                         ▼
┌──────────┐ ┌──────────┐ ┌──────────────────┐ ┌──────────────────┐
│  Agent   │ │  Paper   │ │  Elastic Cloud   │ │  Cloud Storage   │
│  Engine  │ │  Ingest  │ │  (search +       │ │  (PDFs, exports) │
│  (ADK +  │ │  Workers │ │   vector index)  │ │                  │
│  Gemini) │ │          │ │                  │ │                  │
└────┬─────┘ └────┬─────┘ └──────────────────┘ └──────────────────┘
     │            │
     │            ▼
     │      ┌──────────────────────────────────────────────┐
     │      │  External Paper APIs                         │
     │      │  OpenAlex, Semantic Scholar, arXiv,          │
     │      │  bioRxiv, PMC, Crossref, Unpaywall           │
     │      └──────────────────────────────────────────────┘
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Agent Tools (MCP)                                          │
│  - elastic.search   - paper.fetch    - paper.parse          │
│  - methods.extract  - claim.resolve  - chain.trace          │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 Stack by Layer

**Frontend**
- Next.js 14 (App Router) for the web UI
- Tailwind + shadcn/ui for components
- Server-sent events for streaming live agent progress to the user
- Recharts for the reproducibility-score breakdown
- Hosted on Cloud Run with a static asset CDN

**API / Orchestration**
- FastAPI in Python on Cloud Run
- Cloud Tasks for asynchronous job queueing (each paper reconstruction is a job)
- Firestore for job metadata, user history, cached reconstructions
- Cloud Storage for PDFs and exported artifacts (PDF, Markdown, JSON, CSV)

**Agent Layer**
- **Google Agent Development Kit (ADK)** with Gemini 2.5 Pro as the planning/reasoning model and Gemini 2.5 Flash for high-volume sub-tasks (claim classification, sentence-level extraction)
- Vertex AI for model serving
- The agent exposes tools via MCP; the **Elastic MCP server** is the partner integration

**Search & Retrieval (Elastic Track requirement)**
- Elastic Cloud on Google Cloud (the deployment Google's partnership makes easy)
- One primary index: `papers` with fields for full text, methods section (separately indexed for higher boost), references list, claim-level embeddings
- A secondary index: `claims` with extracted methodological claims, their type, their resolution state, their provenance pointers
- Hybrid search: BM25 over methods text + dense vectors (ELSER or text-embedding-005) for semantic claim matching
- Aggregations used for: citation network traversal, "find all papers that cite X for method Y," reproducibility-score corpus-wide analytics

**Document Ingest Pipeline**
- GROBID running on Cloud Run for PDF → structured XML (sections, references, captions)
- Custom post-processor that maps GROBID output to our claim schema
- For arXiv/PMC/bioRxiv: prefer the native XML/HTML when available (cleaner than PDF parsing)
- Reference resolution via Crossref + OpenAlex
- Open-access discovery via Unpaywall before falling back to paywall flagging

**Caching & State**
- Firestore: per-user reconstruction history, exported documents, saved protocols
- Memorystore (Redis): hot cache of resolved papers and intermediate claim resolutions
- Cache key strategy: hash of (paper DOI, agent prompt version, depth cap) — re-runs hit cache unless something changed

**Observability**
- Cloud Logging + Cloud Trace for the agent's tool-call graph
- A custom "agent run viewer" in the admin UI for debugging recursive resolution failures
- (Stretch) Wire into Arize Phoenix for LLM-call observability since it's OpenTelemetry-native — useful even though Arize is a separate track

### 10.3 The Agent Loop (Detailed)

This is the core IP. The agent runs as a planner-executor with a bounded recursion budget.

```
INPUT: paper_id

STEP 1 — Ingest & index
  - Fetch paper, parse to structured form
  - Push into Elastic `papers` index
  - Extract bibliography → resolve all references to canonical IDs

STEP 2 — Methods decomposition (Gemini Pro)
  - Read methods section
  - Extract list of methodological claims, each tagged with:
      type, specificity, cited_ref_ids (if any)
  - Push into Elastic `claims` index linked to paper_id

STEP 3 — Claim resolution loop
  FOR each claim where specificity != "fully_described":
    IF specificity == "shortcut_citation":
      → call tool: chain.resolve(claim, cited_ref_ids, depth=0)
    IF specificity == "standard_unspecified":
      → call tool: standards.lookup(claim) [searches protocol DBs]
    IF specificity == "partially_described":
      → call tool: claim.augment(claim) [searches corpus for completions]

  TOOL chain.resolve(claim, ref_ids, depth):
    IF depth > MAX_DEPTH (5): return TERMINAL_GAP("depth_exceeded")
    FOR ref_id IN ref_ids:
      paper = paper.fetch(ref_id)
      IF paper unavailable: continue → if all fail: TERMINAL_GAP("paywall_or_dead")
      relevant_section = methods.locate(paper, claim)
      IF relevant_section fully describes claim:
        return RESOLVED(text=..., source=ref_id, sentence_ids=...)
      ELIF relevant_section itself shortcuts:
        return chain.resolve(claim, relevant_section.cited_refs, depth+1)
      ELSE:
        continue
    return TERMINAL_GAP("no_match_in_cited_papers")

STEP 4 — Protocol assembly (Gemini Pro)
  - Take all resolved + terminal-gap claims
  - Synthesize into structured protocol document with provenance
  - Produce reproducibility score breakdown

STEP 5 — Gap report
  - List every TERMINAL_GAP with chain trace, suggested action
  - Surface to user
```

**Why this needs an agent, not just RAG:** A vanilla RAG system retrieves once and answers. This system has to decide *what to retrieve next* based on what it just retrieved — a citation in paper A points to paper B, which points to paper C. The decision logic at each step (does this resolve the claim? does it shortcut further? is this the right cited reference among three?) requires a reasoning model in the loop. This is exactly what agentic patterns are for, and exactly what hackathon judges want to see.

### 10.4 Data Models

**`papers` index (Elastic)**
```json
{
  "paper_id": "doi:10.1234/...",
  "title": "...",
  "authors": [...],
  "year": 2021,
  "venue": "...",
  "abstract": "...",
  "full_text": "...",
  "sections": {
    "abstract": "...",
    "introduction": "...",
    "methods": "...",
    "results": "..."
  },
  "methods_sentences": [
    {"sentence_id": 0, "text": "...", "embedding": [...]},
    ...
  ],
  "references": [
    {"ref_id": "1", "doi": "...", "raw_citation": "...", "resolved": true}
  ],
  "open_access_url": "...",
  "ingested_at": "..."
}
```

**`claims` index (Elastic)**
```json
{
  "claim_id": "uuid",
  "paper_id": "doi:10.1234/...",
  "type": "reagent | equipment | procedure | analysis | parameter | dataset",
  "raw_text": "Cells were maintained as described in Smith et al. 2019.",
  "specificity": "shortcut_citation",
  "cited_ref_ids": ["10.1234/smith2019"],
  "resolution_status": "resolved | terminal_gap | unresolved",
  "resolved_text": "...",
  "resolution_chain": [
    {"depth": 0, "source_paper": "doi:10.1234/smith2019", "sentence_ids": [42, 43]},
    {"depth": 1, "source_paper": "doi:10.1234/jones2014", "sentence_ids": [12]}
  ],
  "terminal_gap_reason": null,
  "embedding": [...]
}
```

**Reconstructed Protocol (output, stored in Firestore + Cloud Storage)**
```json
{
  "protocol_id": "uuid",
  "source_paper_id": "...",
  "reproducibility_score": 73,
  "section_scores": {
    "reagents": 90, "equipment": 85, "procedure": 70,
    "analysis": 50, "parameters": 60
  },
  "sections": {
    "reagents": [...],
    "equipment": [...],
    "procedure": [...],
    "analysis": [...]
  },
  "gaps": [
    {
      "claim": "...",
      "reason": "depth_exceeded",
      "chain_trace": [...],
      "suggested_action": "Contact corresponding author of doi:..."
    }
  ],
  "generated_at": "..."
}
```

### 10.5 Why Elastic, specifically

The hackathon requires the partner integration to be *essential*, not bolted on. This system genuinely needs Elastic because:

1. **Hybrid retrieval at scale.** The methods-locator step needs to find the *specific sentences* in a cited paper that match a claim. Pure vector search returns vaguely-related content; pure keyword fails on paraphrased techniques. Elastic's hybrid (BM25 + dense vectors with reranking) is the right primitive.

2. **Aggregations for citation graph reasoning.** "How many other papers cite paper X for method Y?" is an aggregation query, not a retrieval query. Elastic's aggregations make this fast even at corpus scale.

3. **Structured + unstructured in one index.** Claims have structured fields (type, specificity, resolution status) AND embeddings AND raw text. Elastic handles all three natively.

4. **Self-hostable for sensitive corpora.** Real metascience teams often work with embargoed or partially-paywalled corpora. Elastic Cloud or self-hosted Elasticsearch fits both deployment models.

5. **Established corpus connectors.** Logstash and Elastic ingest pipelines handle the ETL from arXiv/PMC/etc. without us writing it from scratch.

---

## 11. Demo Plan (3-minute video script)

**0:00 — Hook (15s).** "0 out of 193. That's how many high-profile cancer papers had methods sections complete enough to reproduce, according to the Reproducibility Project. Methods sections are broken — they punt to other papers, which punt to other papers, until the chain dead-ends."

**0:15 — Problem visualization (20s).** Show a real methods section with shortcut citations highlighted. Click one: "Smith et al. 2019" → that paper's methods section also shortcuts → Jones 2014 → dead URL. The viewer feels the pain.

**0:35 — Tool intro (10s).** "Methods Reconstructor traces every shortcut, assembles a self-contained protocol, and tells you exactly where the chain breaks."

**0:45 — Live demo (1:30).**
- Paste a real arXiv URL
- Watch the agent stream its work: ingesting, decomposing, resolving claims
- Show the agent recursing — "claim X shortcuts to paper Y, fetching, found description at sentence 42"
- Final reconstructed protocol appears with provenance hover-overs
- Show the gap report: "3 items could not be resolved. Suggested action: contact corresponding author for item 2."

**2:15 — Architecture flash (15s).** Quick diagram showing Gemini + ADK + Elastic + Google Cloud, emphasize the agentic recursive loop.

**2:30 — Impact close (30s).** "Researchers spend weeks chasing methodological citation chains. Methods Reconstructor does it in minutes. We're not replacing the scientist — we're killing the bottleneck between them and the experiment."

---

## 12. Appendix: Why this wins on the judging criteria

| Criterion | Why this scores high |
|---|---|
| **Technological Implementation** | Genuine recursive agentic loop, not single-shot RAG; Elastic hybrid search used for what it's actually best at; ADK + Gemini orchestration with clear tool boundaries |
| **Design** | The three-screen UX (input → live agent progress → reconstructed protocol with provenance) is concrete and demos beautifully; the gap report is a novel UI primitive |
| **Potential Impact** | Targets a named, measured, peer-reviewed problem (shortcut citation chains, PLOS Biology 2024) tied to the replication crisis; works on existing papers without requiring author cooperation |
| **Quality of the Idea** | Most submissions will be generic "AI for papers"; this one names a specific structural failure mode and solves it with a specific architecture |
