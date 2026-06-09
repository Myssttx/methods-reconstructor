from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def source_backed(claim: dict[str, Any]) -> bool:
    if claim.get("resolution_status") != "resolved":
        return False
    if claim.get("specificity") == "fully_described":
        return bool(claim.get("raw_text"))
    return any(
        step.get("source_paper_id") and step.get("sentence_ids")
        for step in claim.get("resolution_chain") or []
    )


def examples_from_protocol(protocol: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for claims in (protocol.get("sections") or {}).values():
        for claim in claims:
            if not source_backed(claim):
                continue
            evidence = [
                {
                    "source_paper_id": step.get("source_paper_id"),
                    "sentence_ids": step.get("sentence_ids") or [],
                    "text": step.get("extracted_text") or "",
                }
                for step in claim.get("resolution_chain") or []
                if step.get("source_paper_id") and step.get("sentence_ids")
            ]
            yield {
                "task": "methods_claim_extraction_and_resolution",
                "input": {
                    "paper_id": claim.get("paper_id") or protocol.get("source_paper_id"),
                    "sentence_id": claim.get("raw_sentence_id"),
                    "text": claim.get("raw_text") or "",
                },
                "output": {
                    "type": claim.get("type"),
                    "specificity": claim.get("specificity"),
                    "cited_ref_ids": claim.get("cited_ref_ids") or [],
                    "resolved_text": claim.get("resolved_text") or claim.get("raw_text") or "",
                },
                "evidence": evidence,
                "provenance": {
                    "protocol_id": protocol.get("protocol_id"),
                    "job_id": protocol.get("job_id"),
                    "generated_at": protocol.get("generated_at"),
                    "generation_metadata": protocol.get("generation_metadata") or {},
                    "label_source": "model_generated_source_backed",
                },
            }


def export_jsonl(storage_root: Path, output_path: Path) -> tuple[int, int]:
    reconstruction_root = storage_root / "reconstructions"
    files = sorted(reconstruction_root.glob("*.json"))
    examples = []
    for path in files:
        protocol = json.loads(path.read_text())
        examples.extend(examples_from_protocol(protocol))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output:
        for example in examples:
            output.write(json.dumps(example, ensure_ascii=True) + "\n")
    return len(files), len(examples)
