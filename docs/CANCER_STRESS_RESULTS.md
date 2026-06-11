# Cancer Paper Stress Results

## June 10, 2026 Baseline

The stress harness ran three uncached reconstructions for each of ten public
PMC cancer papers. Completed-claim reuse was disabled deliberately so every
trial exercised Elastic indexing, hybrid retrieval, citation resolution, and
protocol assembly.

- 30 of 30 trials completed.
- 30 of 30 finished below the 120-second target.
- Mean runtime: 15.371 seconds.
- Range: 3.047 to 51.192 seconds.
- The original permissive threshold marked all ten papers stable.
- Nine papers had exact claim-signature and label agreement across all trials.
- The harness now uses exact agreement, so this baseline is nine stable papers.
- The Puram HNSCC paper varied by one inferred claim: minimum signature
  Jaccard 0.9922 and minimum label agreement 0.9961.

Passing the aggregate threshold did not mean every result was scientifically
acceptable. Inspection of the Puram difference found a corpus inference that
matched only generic terms such as hours, wells, and plates, then attached an
unrelated immune-cell incubation method to an SCC9 viral-transduction claim.
Corpus inference now requires method-specific overlap with both the candidate
claim and its resolved evidence. Focused regression tests cover the discovered
failure; the table below remains the pre-fix live baseline and should not be
presented as a post-fix benchmark.

## Paper Set

| PMC | Methods sentences | References | Citation-bearing methods | Shortcut candidates | Mean seconds | Max seconds | Min signature Jaccard |
|---|---:|---:|---:|---:|---:|---:|---:|
| PMC6727976 | 111 | 88 | 12 | 5 | 14.156 | 20.274 | 1.0000 |
| PMC5878932 | 268 | 52 | 15 | 11 | 29.955 | 35.198 | 0.9922 |
| PMC6132072 | 70 | 54 | 2 | 2 | 10.228 | 17.548 | 1.0000 |
| PMC6348010 | 645 | 47 | 37 | 7 | 22.536 | 29.264 | 1.0000 |
| PMC9044823 | 158 | 71 | 31 | 4 | 4.056 | 6.053 | 1.0000 |
| PMC7608385 | 97 | 103 | 0 | 3 | 3.727 | 5.070 | 1.0000 |
| PMC7220853 | 300 | 45 | 0 | 17 | 6.414 | 9.092 | 1.0000 |
| PMC6703186 | 262 | 34 | 15 | 5 | 41.497 | 51.192 | 1.0000 |
| PMC5424158 | 91 | 60 | 10 | 2 | 4.380 | 7.039 | 1.0000 |
| PMC7484178 | 265 | 170 | 33 | 5 | 16.763 | 22.094 | 1.0000 |

The full titles and selection evidence are versioned in
[`eval/cancer_stress_set.json`](../eval/cancer_stress_set.json).

## Bottlenecks

Mean time per trial was concentrated in:

| Stage | Mean time | Share of total |
|---|---:|---:|
| Citation and evidence resolution | 10.081 s | 65.6% |
| Initial Elastic claim indexing | 3.140 s | 20.4% |
| Paper acquisition and ingest | 1.284 s | 8.4% |
| Final Elastic claim indexing | 0.824 s | 5.4% |
| Decomposition and assembly | 0.013 s | <0.1% |

The slowest paper, PMC6703186, averaged 35.323 seconds in resolution because
its citation shortcuts required multiple Gemini locator decisions after Elastic
retrieval. Assembly itself averaged under 2 milliseconds and is not a material
bottleneck.

Failed full-text acquisition was also repeated for metadata-only cited papers.
Those unsuccessful acquisitions are now cached in Elastic for one hour by
default, while successful papers remain cached normally. This reduces repeated
PMC, OpenAlex, Unpaywall, and PDF attempts without permanently suppressing a
source that may become available later.

## Interpretation

The system is operational and fast enough for the current two-minute target,
but the baseline is not a scientific-validity benchmark. Stability metrics can
miss consistently wrong or weak inferences. The next evaluation layer must use
human-reviewed claim and evidence labels, especially for corpus inference and
citation-chain completion.
