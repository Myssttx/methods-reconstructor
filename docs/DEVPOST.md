# Devpost Draft

## Project Name

Methods Reconstructor

## Tagline

An Elastic-centered Gemini research agent that reconstructs difficult
cancer-paper methods and shows exactly where the evidence chain breaks.

## Inspiration

Critical experimental details are often distributed across a chain of papers.
A cancer paper may say that tissue processing, image segmentation, sequencing,
or statistical analysis was "performed as previously described." Following
those citations manually is slow, and the chain may end at a paywall, vague
standard, or missing parameter.

We built Methods Reconstructor to automate the evidence-gathering work without
pretending that a generated protocol is automatically reproducible.

## What It Does

Methods Reconstructor is a functional research agent, not a conversational
wrapper. Given a DOI, PMC ID, URL, arXiv ID, or PDF, it:

1. Creates an explicit reconstruction plan.
2. Parses and indexes the paper in Elastic.
3. Extracts source-linked methodological claims.
4. Detects citation shortcuts and under-specified procedures.
5. Uses Elastic hybrid search to locate supporting method passages.
6. Traverses citation chains recursively.
7. Produces a structured methods reconstruction, evidence score, provenance,
   unresolved-gap report, browser result, and clean PDF export.

## How We Built It

### Google Cloud and Gemini

- Built with **Gemini on Vertex AI** using Google Cloud Application Default
  Credentials.
- Includes a **Google ADK** `root_agent` for Google Cloud Agent Builder/agent
  platform execution.
- Uses Gemini for bounded structured extraction and evidence classification,
  with deterministic fallbacks so one slow model request cannot stall a paper.
- Supports Firestore and Cloud Storage as production persistence layers.

### Elastic Partner Integration

Elastic is the product's indexing, partner MCP/search, retrieval, and evidence
layer. The local implementation uses native Elasticsearch tools, and the
Google ADK entry point attaches an Elastic streamable-HTTP MCP toolset whenever
`ELASTIC_MCP_URL` is configured.

Elastic performs:

- canonical paper and sentence indexing;
- nested dense-vector and BM25 retrieval;
- reciprocal-rank fusion of retrieval results;
- claim-corpus indexing with structured status and provenance;
- citation-resolution cache lookup;
- evidence search for the Google ADK agent.

This integration is essential. Without Elastic, the agent cannot locate
specific cited passages, reuse parsed evidence, or search the structured claim
corpus.

## Architecture

```text
Google ADK / Next.js
        |
FastAPI AgentRunner
        |
        +--> Gemini on Vertex AI
        +--> Elastic papers + claims indexes
        +--> PMC / OpenAlex / Crossref / Unpaywall
        +--> Firestore or local persistence
        |
Reconstructed methods + evidence chains + gaps + PDF
```

## Real-World Problem

The target user is a researcher, reviewer, or metascience team evaluating
whether a published cancer experiment contains enough traceable methodological
evidence to reproduce. The system reduces manual citation chasing while keeping
source boundaries visible.

## What Makes It Agentic

The agent does not answer from one retrieved context window. It:

- plans a multi-stage workflow;
- chooses and executes ingestion, extraction, Elastic search, citation fetch,
  and result-reading tools;
- maintains state across claims and citation depths;
- recursively follows new references discovered during resolution;
- stops at explicit depth, time, and token budgets;
- records failures as gaps rather than inventing missing methods.

## Challenges

- Public papers have inconsistent XML/PDF structure.
- Some methods sections include large tables and figure captions that should
  not become protocol claims.
- Citation identifiers differ across PMC, GROBID, and publisher formats.
- LLM latency is highly variable for large structured outputs.
- Evidence coverage must not be mislabeled as validated reproducibility.

We addressed these with parser versioning, source-span validation, bounded
hybrid extraction, deterministic large-paper fallbacks, citation-fetch
deduplication, and explicit evidence semantics.

## Accomplishments

- Reconstructed a complex Puram cancer paper in about 1.7 seconds uncached
  after removing an unbounded multi-call extraction path.
- Reconstructed the Keren multiplexed-imaging paper in about 1.4 seconds.
- Added completed-claim caching, bringing a repeated Puram run to about 190 ms.
- Preserved Elastic as the central retrieval and evidence system throughout.
- Added source-listed PDF export and browser-readable results.
- Added a fixed public cancer-paper stress suite and variability harness.

These timings are local development measurements, not a cloud-service SLA.

## What We Learned

The difficult part is not generating plausible methods prose. It is preserving
evidence identity across parser boundaries, search results, citation depth, and
model fallbacks. Fast generation without provenance would make the product less
useful, not more useful.

## What's Next

- Deploy the ADK agent through Google Cloud's managed agent runtime.
- Connect an Elastic Agent Builder MCP endpoint where supported.
- Replace the process-local runner registry with a durable queue.
- Build a human-reviewed benchmark for claim type, citation resolution, and
  evidence coverage.
- Add corpus-level citation dependency analytics in Elastic.

## Built With

- Gemini 3.0 on Vertex AI
- Google Agent Development Kit / Google Cloud Agent Builder entry point
- Elasticsearch / Elastic Cloud
- FastAPI
- Next.js
- Firestore and Cloud Storage support
- PMC, OpenAlex, Crossref, Unpaywall, arXiv, and GROBID

## Important Limitation

Methods Reconstructor reports traceable methods evidence coverage. It does not
certify that a study is reproducible or scientifically correct.
