from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "backend"))
sys.path.insert(0, str(project_root))

from app.agent.runner import AgentRunner
from app.evaluation.variability import claims_from_protocol, variability_report
from app.llm.gemini_client import active_llm_provider
from app.logging import configure_logging
from app.search.elastic_client import close_es
from app.storage.firestore_client import get_store


def _stats(values: list[float], *, digits: int = 3) -> dict[str, float]:
    if not values:
        return {}
    average = mean(values)
    return {
        "mean": round(average, digits),
        "min": round(min(values), digits),
        "max": round(max(values), digits),
        "cv": (
            round(pstdev(values) / average, 4)
            if len(values) > 1 and average
            else 0.0
        ),
    }


def _protocol_claims(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        claim
        for section_claims in (protocol.get("sections") or {}).values()
        for claim in section_claims
    ]


def _pathway_summary(protocol: dict[str, Any]) -> dict[str, Any]:
    claims = _protocol_claims(protocol)
    gaps = protocol.get("gaps") or []
    claim_chains = [
        claim.get("resolution_chain") or []
        for claim in claims
        if claim.get("resolution_chain")
    ]
    gap_chains = [
        gap.get("chain_trace") or []
        for gap in gaps
        if gap.get("chain_trace")
    ]
    chains = [*claim_chains, *gap_chains]
    chain_depths = [len(chain) for chain in chains]
    evidence_sources = {
        step.get("source_paper_id")
        for chain in chains
        for step in chain
        if step.get("source_paper_id")
    }
    metadata = protocol.get("generation_metadata") or {}
    return {
        "claim_count": len(claims) + len(gaps),
        "protocol_claim_count": len(claims),
        "gap_count": len(gaps),
        "methods_evidence_score": protocol.get("methods_evidence_score"),
        "specificity_counts": dict(
            Counter(
                str(item.get("specificity") or "unknown")
                for item in [*claims, *gaps]
            )
        ),
        "resolution_status_counts": dict(
            Counter(str(claim.get("resolution_status") or "unknown") for claim in claims)
            | Counter({"terminal_gap": len(gaps)})
        ),
        "gap_reason_counts": dict(
            Counter(str(gap.get("reason") or "unknown") for gap in gaps)
        ),
        "citation_chain_count": len(chains),
        "resolved_citation_chain_count": len(claim_chains),
        "failed_citation_chain_count": len(gap_chains),
        "citation_chain_depth": _stats([float(depth) for depth in chain_depths]),
        "distinct_evidence_sources": len(evidence_sources),
        "extraction_mode": metadata.get("extraction_mode"),
        "assembly_mode": metadata.get("assembly_mode"),
    }


async def run_once(
    entry: dict[str, Any],
    target_seconds: float,
    run_number: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    identifier = entry["identifier"]
    job_id = f"cancer-stress-{run_number}-{uuid.uuid4()}"
    runner = AgentRunner(
        job_id=job_id,
        identifier=identifier,
        reuse_cached_claims=False,
    )
    await runner.run()

    store = get_store()
    job = await store.get_job(job_id) or {}
    protocol = (
        await store.get_reconstruction(job["protocol_id"])
        if job.get("protocol_id")
        else None
    )
    timings = {
        key: round(float(value), 1)
        for key, value in (job.get("timings_ms") or {}).items()
    }
    total_seconds = round(float(timings.get("total", 0)) / 1000, 3)
    result = {
        "run_number": run_number,
        "run_kind": "initial" if run_number == 1 else "repeat",
        "job_id": job_id,
        "status": job.get("status"),
        "error": job.get("error"),
        "timings_ms": timings,
        "total_seconds": total_seconds,
        "within_target": bool(total_seconds and total_seconds <= target_seconds),
    }
    if protocol:
        result["pathway"] = _pathway_summary(protocol)
    return result, protocol


def _paper_summary(
    trials: list[dict[str, Any]],
    protocols: list[dict[str, Any]],
    target_seconds: float,
) -> dict[str, Any]:
    complete_trials = [trial for trial in trials if trial["status"] == "complete"]
    total_seconds = [trial["total_seconds"] for trial in complete_trials]
    stages = sorted(
        {
            stage
            for trial in complete_trials
            for stage in trial.get("timings_ms", {})
        }
    )
    stage_stats = {
        stage: _stats(
            [
                float(trial["timings_ms"][stage])
                for trial in complete_trials
                if stage in trial["timings_ms"]
            ],
            digits=1,
        )
        for stage in stages
    }
    complete_pathways = [
        trial["pathway"]
        for trial in complete_trials
        if trial.get("pathway")
    ]
    extraction_modes = sorted(
        {
            str(pathway.get("extraction_mode"))
            for pathway in complete_pathways
        }
    )
    assembly_modes = sorted(
        {
            str(pathway.get("assembly_mode"))
            for pathway in complete_pathways
        }
    )
    gap_counts = [int(pathway["gap_count"]) for pathway in complete_pathways]
    evidence_scores = [
        float(pathway["methods_evidence_score"])
        for pathway in complete_pathways
        if pathway.get("methods_evidence_score") is not None
    ]
    variability = (
        variability_report([claims_from_protocol(protocol) for protocol in protocols])
        if len(protocols) >= 2
        else None
    )
    stable = bool(
        len(complete_trials) == len(trials)
        and variability
        and variability["claim_count_min"] == variability["claim_count_max"]
        and variability["pairwise_signature_jaccard_min"] == 1.0
        and variability["pairwise_label_agreement_min"] == 1.0
        and len(set(gap_counts)) == 1
        and len(extraction_modes) == 1
        and len(assembly_modes) == 1
    )
    repeat_seconds = [
        trial["total_seconds"]
        for trial in complete_trials
        if trial["run_kind"] == "repeat"
    ]
    initial_seconds = next(
        (
            trial["total_seconds"]
            for trial in complete_trials
            if trial["run_kind"] == "initial"
        ),
        0.0,
    )
    return {
        "n_trials": len(trials),
        "n_complete": len(complete_trials),
        "all_within_target": bool(
            complete_trials
            and len(complete_trials) == len(trials)
            and all(trial["within_target"] for trial in complete_trials)
        ),
        "target_seconds": target_seconds,
        "total_seconds": _stats(total_seconds),
        "repeat_speedup_vs_initial": (
            round(initial_seconds / mean(repeat_seconds), 3)
            if initial_seconds and repeat_seconds and mean(repeat_seconds)
            else None
        ),
        "stage_timings_ms": stage_stats,
        "variability": variability,
        "gap_count": _stats([float(value) for value in gap_counts]),
        "methods_evidence_score": _stats(evidence_scores),
        "extraction_modes": extraction_modes,
        "assembly_modes": assembly_modes,
        "stable": stable,
    }


async def run_paper(
    entry: dict[str, Any],
    target_seconds: float,
    n_runs: int,
) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    protocols: list[dict[str, Any]] = []
    for run_number in range(1, n_runs + 1):
        print(f"  trial {run_number}/{n_runs}")
        trial, protocol = await run_once(entry, target_seconds, run_number)
        trials.append(trial)
        if protocol:
            protocols.append(protocol)
        print(
            f"    status={trial['status']} total={trial['total_seconds']}s "
            f"gaps={(trial.get('pathway') or {}).get('gap_count', '-')}"
        )
    return {
        "identifier": entry["identifier"],
        "title": entry.get("title"),
        "complexity": entry.get("complexity") or [],
        "access_expectation": entry.get("access_expectation"),
        "selection_evidence": entry.get("selection_evidence") or {},
        "summary": _paper_summary(trials, protocols, target_seconds),
        "trials": trials,
    }


async def evaluate(
    set_path: Path,
    target_seconds: float,
    n_runs: int,
    limit: int | None = None,
    identifiers: set[str] | None = None,
) -> dict[str, Any]:
    configure_logging()
    payload = json.loads(set_path.read_text())
    entries = payload.get("papers") or []
    if identifiers:
        entries = [entry for entry in entries if entry["identifier"] in identifiers]
        matched = {entry["identifier"] for entry in entries}
        missing = identifiers - matched
        if missing:
            raise ValueError(
                f"Identifiers not present in stress set: {', '.join(sorted(missing))}"
            )
    if limit is not None:
        entries = entries[:limit]
    results = []
    try:
        for index, entry in enumerate(entries, start=1):
            print(f"[{index}/{len(entries)}] {entry['identifier']} - {entry.get('title', '')}")
            results.append(await run_paper(entry, target_seconds, n_runs))
    finally:
        await close_es()

    trials = [trial for result in results for trial in result["trials"]]
    complete_trials = [trial for trial in trials if trial["status"] == "complete"]
    totals = [trial["total_seconds"] for trial in complete_trials]
    stable_papers = [result for result in results if result["summary"]["stable"]]
    within_target = [trial for trial in complete_trials if trial["within_target"]]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": active_llm_provider(),
        "target_seconds": target_seconds,
        "runs_per_paper": n_runs,
        "summary": {
            "n_papers": len(results),
            "n_trials": len(trials),
            "n_complete": len(complete_trials),
            "n_failed": len(trials) - len(complete_trials),
            "n_within_target": len(within_target),
            "n_stable_papers": len(stable_papers),
            "completion_rate": (
                round(len(complete_trials) / len(trials), 4)
                if trials
                else 0.0
            ),
            "total_seconds": _stats(totals),
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run repeated reconstructions over complex public cancer papers and "
            "measure timing, pathway stability, and output variability."
        )
    )
    parser.add_argument(
        "--set",
        default=str(Path(__file__).parent / "cancer_stress_set.json"),
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent / "reports" / "cancer-stress-latest.json"),
    )
    parser.add_argument("--target-seconds", type=float, default=120.0)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--identifier",
        action="append",
        dest="identifiers",
        help="Run only this stress-set identifier; may be repeated.",
    )
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs must be at least 2")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    report = asyncio.run(
        evaluate(
            Path(args.set),
            args.target_seconds,
            args.runs,
            args.limit,
            set(args.identifiers or []),
        )
    )
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
