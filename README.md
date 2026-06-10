# Methods Reconstructor

Methods Reconstructor is a functional research agent that reconstructs difficult
cancer-paper methodologies from source text and citation chains. It plans the
work, indexes evidence in Elastic, retrieves cited procedures with hybrid
search, follows methods citations recursively, and produces a structured
methods reconstruction with explicit gaps and provenance.

Built for the **Google Cloud Rapid Agent Hackathon, Elastic partner track**.

## Why It Exists

Cancer papers frequently describe critical procedures with phrases such as
"performed as previously described." The cited paper may point to another
paper, use a vague standard, or omit a parameter entirely. Researchers then
spend hours manually traversing references before they can judge whether an
experiment can be repeated.

Methods Reconstructor turns that process into an auditable agent workflow:

1. Plan the reconstruction.
2. Resolve and parse the paper.
3. Index methods sentences, references, vectors, and claims in Elastic.
4. Detect fully described methods, partial descriptions, vague standards, and
   citation shortcuts.
5. Retrieve cited evidence with Elastic BM25 and dense-vector search fused by
   reciprocal rank fusion.
6. Follow citation chains recursively.
7. Produce a source-linked protocol, methods-evidence score, gap report, and
   clean PDF export.

This is not a chatbot and it is not single-shot RAG. The agent executes a
bounded research workflow and persists its evidence and results.

## Hackathon Stack

- **Gemini and Google Cloud:** Gemini 3.0 models run through Vertex AI using
  Application Default Credentials. A Google ADK entry point in
  [`backend/methods_agent/agent.py`](backend/methods_agent/agent.py) exposes the
  production reconstruction pipeline for Google Cloud Agent Builder/agent
  platform workflows.
- **Elastic partner layer:** Elasticsearch is the required indexing, evidence,
  hybrid-search, citation-resolution, and claim-corpus layer. The ADK agent
  accesses it through explicit search tools. Local development uses the native
  Elastic Python client. If `ELASTIC_MCP_URL` is configured, the ADK agent also
  attaches the Elastic streamable-HTTP MCP toolset.
- **Application:** FastAPI runs the agent pipeline and streams events to a
  Next.js interface. Firestore and Cloud Storage are optional production
  persistence targets.

## Why Elastic Is Central

Elastic is not an added document store. The reconstruction depends on it:

1. **Evidence index:** parsed papers, source sentence IDs, bibliography
   metadata, vectors, and parser versions live in the `papers` index.
2. **Hybrid retrieval:** BM25 and nested dense-vector rankings locate the
   specific procedure passage inside a cited paper. Client-side RRF combines
   the rankings.
3. **Citation resolution:** each recursive step checks indexed evidence before
   fetching and parsing another source.
4. **Claim corpus:** extracted claims combine keyword fields, text, vectors,
   provenance hashes, resolution status, and evidence chains in one index.
5. **Repeatability:** completed, version-matched claim sets are reused instead
   of regenerating the same paper.

Removing Elastic removes the evidence retrieval and citation-resolution core of
the product.

## Architecture

```text
Next.js UI ──SSE/HTTP──> FastAPI research-agent runner
                              │
Google ADK root_agent ────────┤  same production tools
                              │
                              ├──> Gemini on Vertex AI
                              ├──> Elasticsearch / Elastic Cloud
                              ├──> PMC, OpenAlex, Crossref, Unpaywall, arXiv
                              └──> Firestore / local result store

Elastic papers index: source text, references, sentence vectors
Elastic claims index: claims, provenance, embeddings, resolution chains
```

## Local Setup

Prerequisites:

- Docker Desktop or Colima
- Git
- Optional: Google Cloud CLI for live Gemini calls

```bash
git clone https://github.com/Myssttx/methods-reconstructor.git
cd methods-reconstructor
cp .env.example .env
make dev
```

In another terminal:

```bash
make elastic-init
make seed
```

Open:

- Product: http://localhost:3000
- API health: http://localhost:8000/api/health
- Elasticsearch: http://localhost:9200

The offline provider supports a credential-free demo. Elastic remains real in
offline mode.

## Vertex AI Authentication

The project uses Google Cloud Application Default Credentials, not a committed
service-account key:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

Set `GCP_PROJECT_ID` and `GOOGLE_CLOUD_PROJECT` in the ignored local `.env`.
The Docker stack mounts the standard ADC file read-only.

## Google ADK Demo

Install the optional ADK dependency:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e '.[gcp,dev]'
cd ..
make adk-web
```

Open the URL printed by ADK and ask:

```text
Reconstruct the methods for DOI 10.1016/j.cell.2018.08.039.
Show the plan, evidence coverage, unresolved gaps, and the Elastic search role.
```

The ADK agent calls the same `AgentRunner`, Elastic indexes, citation resolver,
and result store used by the website. An Elastic Agent Builder MCP endpoint can
be added with `ELASTIC_MCP_URL` and the ignored `ELASTIC_MCP_AUTH_TOKEN`.

## Website Demo

1. Open http://localhost:3000/tool.
2. Submit `10.1016/j.cell.2018.08.039` or another public DOI/PMC identifier.
3. Watch ingestion, decomposition, citation resolution, assembly, and timing
   events.
4. Read the reconstructed methods and gap report in the browser.
5. Export the result as a source-listed PDF.

For repeatable evaluation:

```bash
make cancer-stress
make variability ID=10.1038/s41586-019-1876-x RUNS=3
```

## Verification

```bash
make secret-scan
make test-unit
cd frontend && npm run build
```

The secret scan checks that `.env`, `aayush_env.txt`, and common credential
signatures are not tracked.

## Evidence Semantics

The displayed score is **methods evidence coverage**: the percentage of
extracted methodological claims backed by source-paper text or sentence-level
evidence from a cited paper. It is not proof that the experiment is
reproducible, scientifically valid, or complete.

The current system is a research prototype. Its main remaining production gap
is access to full text for methods hidden behind publisher paywalls. It uses a
durable Redis worker queue, API-key authentication, SSRF-hardened ingestion,
bounded jobs, and isolated Docker networks.

## Future Improvements

When the recursive resolver cannot legally retrieve a cited paper, it records a
`source_unavailable` terminal gap. Planned improvements include:

1. Expand Unpaywall and institutional-repository discovery for lawful open
   versions.
2. Add user-authorized institutional library access without storing university
   credentials in the application.
3. Support publisher text-and-data-mining APIs using user-provided credentials.

## Repository Layout

```text
backend/   FastAPI pipeline, Google ADK agent, Gemini clients, exports
frontend/  Next.js product interface
infra/     Elastic mappings and Google Cloud bootstrap utilities
eval/      Cancer-paper stress and variability harnesses
docs/      Architecture, deployment, evaluation, and Devpost material
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
