from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.agent.runner import AgentRunner  # noqa: E402
from app.llm.gemini_client import active_llm_provider  # noqa: E402
from app.logging import configure_logging  # noqa: E402
from app.search.elastic_client import close_es  # noqa: E402
from app.storage.firestore_client import get_store  # noqa: E402


async def run_paper(entry: dict, target_seconds: float) -> dict:
    identifier = entry["identifier"]
    job_id = f"cancer-stress-{uuid.uuid4()}"
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
    timings = job.get("timings_ms") or {}
    total_seconds = round(float(timings.get("total", 0)) / 1000, 2)
    n_claims = sum(
        len(claims)
        for claims in ((protocol or {}).get("sections") or {}).values()
    )
    n_gaps = len((protocol or {}).get("gaps") or [])
    total_claims = n_claims + n_gaps

    return {
        "identifier": identifier,
        "title": entry.get("title"),
        "complexity": entry.get("complexity") or [],
        "access_expectation": entry.get("access_expectation"),
        "job_id": job_id,
        "status": job.get("status"),
        "error": job.get("error"),
        "timings_ms": timings,
        "total_seconds": total_seconds,
        "within_target": bool(total_seconds and total_seconds <= target_seconds),
        "n_protocol_claims": n_claims,
        "n_gaps": n_gaps,
        "gap_rate": round(n_gaps / total_claims, 4) if total_claims else None,
        "methods_evidence_score": (protocol or {}).get("methods_evidence_score"),
    }


async def evaluate(set_path: Path, target_seconds: float) -> dict:
    configure_logging()
    payload = json.loads(set_path.read_text())
    results = []
    try:
        for index, entry in enumerate(payload.get("papers") or [], start=1):
            print(
                f"[{index}/{len(payload.get('papers') or [])}] "
                f"{entry['identifier']} - {entry.get('title', '')}"
            )
            result = await run_paper(entry, target_seconds)
            results.append(result)
            print(
                f"  status={result['status']} total={result['total_seconds']}s "
                f"claims={result['n_protocol_claims']} gaps={result['n_gaps']}"
            )
    finally:
        await close_es()

    completed = [result for result in results if result["status"] == "complete"]
    within_target = [result for result in completed if result["within_target"]]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": active_llm_provider(),
        "target_seconds": target_seconds,
        "summary": {
            "n_papers": len(results),
            "n_complete": len(completed),
            "n_failed": len(results) - len(completed),
            "n_within_target": len(within_target),
            "completion_rate": round(len(completed) / len(results), 4) if results else 0,
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stress Methods Reconstructor with complex public cancer papers."
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
    args = parser.parse_args()

    report = asyncio.run(evaluate(Path(args.set), args.target_seconds))
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
