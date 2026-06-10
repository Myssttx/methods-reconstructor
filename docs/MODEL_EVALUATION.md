# Model Evaluation and Training Data

## Variability

Generation now defaults to temperature `0.0`, but that does not guarantee
identical Vertex AI outputs. Run the complete pipeline repeatedly:

```bash
ELASTIC_URL=http://localhost:9200 \
  backend/.venv/bin/python eval/run_variability.py fixture:paper_a --runs 3
```

The report records prompt version, model names, claim-count variation,
pairwise claim-signature Jaccard, and label agreement. For a live paper, keep
the same Elastic index and model configuration across runs so the comparison
isolates model/runtime variability.

## Training-data export

Existing local reconstructions can be converted to provider-neutral JSONL:

```bash
backend/.venv/bin/python eval/export_training_jsonl.py
```

The exporter keeps:

- directly described claims with source sentence IDs;
- citation-chain resolutions backed by retrieved sentence IDs.

It rejects inferred claims, terminal gaps, and resolutions whose chain has no
sentence-level evidence.

This file is filtered pseudo-label data, not gold data. It is useful for prompt
regression tests, retrieval reranking experiments, and later supervised tuning
after a human-reviewed validation split exists. Training directly on all
model-generated labels would be methodologically weak and can reinforce errors.

## Cancer stress suite

The repository includes ten PMC-hosted cancer papers covering single-cell
sequencing, spatial transcriptomics, imaging mass cytometry, and multiplexed
ion beam imaging:

```bash
make cancer-stress
```

Each paper runs three times by default. The report records ingestion,
decomposition, indexing, resolution, assembly, and total time, plus claim
variation, label agreement, extraction-path consistency, citation-chain depth,
gap reasons, evidence coverage, and the exact failure message. The default
performance target is two minutes per trial. A paper is marked stable only when
claim counts, claim signatures, labels, gap counts, and processing modes are
identical across all runs.

Run one or more selected papers while debugging:

```bash
backend/.venv/bin/python eval/run_cancer_stress.py \
  --identifier PMC5878932 \
  --identifier PMC6703186 \
  --runs 3
```

The measured June 10, 2026 baseline and paper list are in
[`docs/CANCER_STRESS_RESULTS.md`](CANCER_STRESS_RESULTS.md).

The default hybrid extractor uses Gemini below 40 source sentences and switches
directly to deterministic, sentence-linked extraction at 40 sentences or more.
Gemini chunks have a 15-second ceiling and failed chunks fall back independently
without discarding successful chunks. Claims and protocol metadata record which
extraction mode was used.
