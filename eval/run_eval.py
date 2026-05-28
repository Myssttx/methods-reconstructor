"""Eval harness skeleton.

Runs the agent against each paper in eval_set.json and reports per-paper:
  - number of claims extracted
  - number of shortcuts detected
  - final reproducibility score

Requires a live Elasticsearch. Real evals would compare against a hand-
annotated ground truth; this stub is the place to grow that out.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.agent.runner import AgentRunner  # noqa: E402
from app.ingest.fixtures import load_all_fixtures  # noqa: E402
from app.ingest.pipeline import _index_with_sentences  # noqa: E402
from app.logging import configure_logging  # noqa: E402
from app.search.indexes import ensure_indexes  # noqa: E402
from app.storage.firestore_client import get_store  # noqa: E402


async def evaluate(eval_set_path: Path) -> list[dict]:
    configure_logging()
    await ensure_indexes()
    for p in load_all_fixtures():
        await _index_with_sentences(p)

    eval_set = json.loads(eval_set_path.read_text())
    results = []

    for entry in eval_set.get("papers", []):
        identifier = entry["identifier"]
        runner = AgentRunner(job_id=f"eval-{identifier}", identifier=identifier)
        task = asyncio.create_task(runner.run())
        async for ev in runner.stream():
            if ev.type in {"complete", "error"}:
                break
        await task

        store = get_store()
        job = await store.get_job(runner.job_id)
        proto = (
            await store.get_reconstruction(job["protocol_id"])
            if job and job.get("protocol_id")
            else None
        )

        results.append(
            {
                "identifier": identifier,
                "ok": proto is not None,
                "score": (proto or {}).get("reproducibility_score"),
                "n_sections": len((proto or {}).get("sections") or {}),
                "n_gaps": len((proto or {}).get("gaps") or []),
            }
        )

    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=str(Path(__file__).parent / "eval_set.json"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "reports" / "latest.json"))
    args = ap.parse_args()

    results = asyncio.run(evaluate(Path(args.set)))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))

    for r in results:
        print(f"  {r['identifier']:30s} score={r.get('score')} gaps={r.get('n_gaps')}")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
