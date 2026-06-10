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
from app.config import get_settings  # noqa: E402
from app.evaluation.variability import claims_from_protocol, variability_report  # noqa: E402
from app.llm.gemini_client import active_llm_provider  # noqa: E402
from app.logging import configure_logging  # noqa: E402
from app.search.elastic_client import close_es  # noqa: E402
from app.storage.firestore_client import get_store  # noqa: E402


async def run_once(identifier: str, run_number: int) -> dict:
    job_id = f"variability-{run_number}-{uuid.uuid4()}"
    runner = AgentRunner(
        job_id=job_id,
        identifier=identifier,
        reuse_cached_claims=False,
    )
    await runner.run()
    job = await get_store().get_job(job_id)
    if not job or job.get("status") != "complete" or not job.get("protocol_id"):
        raise RuntimeError((job or {}).get("error") or f"Run {run_number} failed")
    protocol = await get_store().get_reconstruction(job["protocol_id"])
    if protocol is None:
        raise RuntimeError(f"Run {run_number} completed without a protocol")
    return protocol


async def evaluate(identifier: str, n_runs: int) -> dict:
    configure_logging()
    protocols = []
    try:
        for run_number in range(1, n_runs + 1):
            print(f"Running {run_number}/{n_runs}: {identifier}")
            protocols.append(await run_once(identifier, run_number))
    finally:
        await close_es()

    settings = get_settings()
    claims = [claims_from_protocol(protocol) for protocol in protocols]
    return {
        "identifier": identifier,
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": active_llm_provider(),
        "prompt_version": settings.app_prompt_version,
        "temperature": settings.llm_temperature,
        "decomposition_model": settings.gemini_model_flash,
        "assembly_model": settings.gemini_model_pro,
        "metrics": variability_report(claims),
        "runs": [
            {
                "job_id": protocol.get("job_id"),
                "protocol_id": protocol.get("protocol_id"),
                "claim_count": len(run_claims),
                "methods_evidence_score": protocol.get("methods_evidence_score"),
                "gap_count": len(protocol.get("gaps") or []),
            }
            for protocol, run_claims in zip(protocols, claims, strict=True)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full reconstruction repeatedly and measure output variability."
    )
    parser.add_argument("identifier", help="DOI, arXiv ID, PMC ID, URL, path, or fixture ID")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent / "reports" / "variability-latest.json"),
    )
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs must be at least 2")

    report = asyncio.run(evaluate(args.identifier, args.runs))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report["metrics"], indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
