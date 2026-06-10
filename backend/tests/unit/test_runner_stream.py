import asyncio
import hashlib

import pytest

from app.agent import runner
from app.agent.runner import AgentRunner, _error_message, _load_cached_claims
from app.config import Settings
from app.models import (
    Claim,
    ClaimType,
    Paper,
    PaperSource,
    ResolutionStatus,
    Section,
    Specificity,
)


def test_error_message_falls_back_to_exception_type():
    assert _error_message(TimeoutError()) == "TimeoutError"


@pytest.mark.asyncio
async def test_runner_stream_fans_out_to_multiple_subscribers():
    runner = AgentRunner(job_id="fanout-test", identifier="fixture:paper_a")

    async def next_event():
        async for event in runner.stream():
            return event
        return None

    first = asyncio.create_task(next_event())
    second = asyncio.create_task(next_event())
    await asyncio.sleep(0)

    await runner._emit("status", {"message": "shared"})

    first_event, second_event = await asyncio.gather(first, second)
    assert first_event is not None and first_event.data["message"] == "shared"
    assert second_event is not None and second_event.data["message"] == "shared"


@pytest.mark.asyncio
async def test_completed_claim_cache_requires_matching_methods_and_version(monkeypatch):
    settings = Settings(
        app_prompt_version="v1",
        gemini_model_flash="flash-model",
        llm_temperature=0.0,
    )
    paper = Paper(
        paper_id="paper",
        source=PaperSource.UPLOAD,
        title="Paper",
        sections={"methods": Section(name="methods", text="[0] Wash cells.")},
    )
    claim = Claim(
        claim_id="claim",
        paper_id="paper",
        type=ClaimType.PROCEDURE,
        raw_text="Wash cells.",
        raw_sentence_id=0,
        specificity=Specificity.FULLY_DESCRIBED,
        resolution_status=ResolutionStatus.RESOLVED,
        resolved_text="Wash cells.",
        extraction_version=settings.methods_extraction_version,
        source_methods_hash=hashlib.sha256(paper.methods_text().encode()).hexdigest(),
    )

    monkeypatch.setattr(runner, "get_settings", lambda: settings)
    monkeypatch.setattr(
        runner,
        "claims_for_paper",
        lambda _paper_id: asyncio.sleep(0, result=[claim.model_dump(mode="json")]),
    )

    cached = await _load_cached_claims(paper)

    assert cached == [claim]

    paper.sections["methods"] = Section(name="methods", text="[0] Wash cells three times.")
    assert await _load_cached_claims(paper) == []
