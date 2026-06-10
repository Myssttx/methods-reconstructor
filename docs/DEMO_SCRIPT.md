# Demo script (3-minute video)

## 0:00 — Hook (15s)
"0 out of 193. That's how many high-profile cancer papers had methods sections complete enough to reproduce, according to the Reproducibility Project: Cancer Biology. Methods sections are broken — they punt to other papers, which punt to other papers, until the chain dead-ends."

## 0:15 — Problem visualization (20s)
Show the live `paper_a` fixture in the UI with shortcut citations highlighted. Click one: `Bremer et al. 2021` → that paper's methods also shortcut → `Okamoto et al. 2016` → actually describes the procedure. The viewer feels the chain.

## 0:35 — Tool intro (10s)
"Methods Reconstructor traces every shortcut, assembles a self-contained protocol, and tells you exactly where the chain breaks."

## 0:45 — Live demo (1:30)
- Click "Demo: scRNA-seq with citation chain" on the landing page
- Watch the right-side agent stream: ingest → decompose → claim_resolved → chain.fetching → chain.fetching at depth 1 → resolved
- Final reconstructed protocol appears, organized by section
- Hover any claim → see the chain trace back to the actual source paper
- Switch to the Gap report tab — show the one item that couldn't resolve and its suggested next step

## 2:15 — Architecture flash (15s)
Show the Google ADK/FastAPI agent calling Elastic hybrid search during citation
resolution, with Gemini on Vertex AI handling bounded reasoning tasks.

## 2:30 — Impact close (30s)
"Researchers spend weeks chasing methodological citation chains. Methods Reconstructor does it in minutes. We're not replacing the scientist — we're killing the bottleneck between them and the experiment."
