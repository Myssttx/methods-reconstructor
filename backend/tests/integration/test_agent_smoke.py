"""End-to-end smoke test against a live Elasticsearch.

Skipped when ES isn't reachable (so this doesn't break CI on the laptop).
Run with the stack up via `make dev`.
"""

import asyncio
import os

import httpx
import pytest

ELASTIC_URL = os.environ.get("ELASTIC_URL", "http://localhost:9200")


def _es_alive() -> bool:
    try:
        r = httpx.get(f"{ELASTIC_URL}/_cluster/health", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _es_alive(), reason="elasticsearch not reachable")


@pytest.mark.asyncio
async def test_end_to_end_fixture_chain():
    from app.agent.runner import AgentRunner
    from app.ingest.fixtures import load_all_fixtures
    from app.ingest.pipeline import _index_with_sentences
    from app.search.claims_dao import claims_for_paper
    from app.search.elastic_client import close_es
    from app.search.indexes import ensure_indexes

    try:
        await ensure_indexes()
        for p in load_all_fixtures():
            await _index_with_sentences(p)

        async def run(job_id: str):
            runner = AgentRunner(job_id=job_id, identifier="fixture:paper_a")
            task = asyncio.create_task(runner.run())
            final_event = None
            async for ev in runner.stream():
                if ev.type in {"complete", "error"}:
                    final_event = ev
                    break
            await task
            assert final_event is not None
            assert final_event.type == "complete"

        await run("smoke-test")
        first_claims = await claims_for_paper("fixture:paper_a")
        await run("smoke-test-repeat")
        second_claims = await claims_for_paper("fixture:paper_a")

        assert len(first_claims) == len(second_claims)
        assert {c["claim_id"] for c in first_claims} == {
            c["claim_id"] for c in second_claims
        }
    finally:
        await close_es()
