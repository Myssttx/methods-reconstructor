import asyncio
import json

import pytest

from app.agent.tools import methods_extract
from app.agent.tools.methods_extract import extract_claims
from app.config import Settings
from app.models import Paper, PaperSource, Section


@pytest.mark.asyncio
async def test_claim_ids_are_stable_across_repeated_extraction():
    paper = Paper(
        paper_id="doi:10.1000/stable",
        source=PaperSource.UPLOAD,
        title="Stable claims",
        sections={
            "methods": Section(
                name="methods",
                text="[0] Cells were washed twice with PBS.\n"
                "[1] Images were segmented using Tool X.",
            )
        },
    )

    first = await extract_claims(paper)
    second = await extract_claims(paper)

    assert [claim.claim_id for claim in first] == [claim.claim_id for claim in second]


@pytest.mark.asyncio
async def test_fabricated_claim_text_is_rejected(monkeypatch):
    class FabricatingLLM:
        async def complete(self, **_kwargs):
            return json.dumps(
                {
                    "claims": [
                        {
                            "type": "procedure",
                            "specificity": "fully_described",
                            "cited_ref_ids": [],
                            "raw_text": "A fabricated procedure.",
                            "raw_sentence_id": 0,
                        }
                    ]
                }
            )

    monkeypatch.setattr(methods_extract, "get_llm", lambda: FabricatingLLM())
    paper = Paper(
        paper_id="paper",
        source=PaperSource.UPLOAD,
        title="Paper",
        sections={
            "methods": Section(
                name="methods",
                text="[0] Cells were washed twice with PBS.",
            )
        },
    )

    with pytest.raises(RuntimeError, match="no methodological claims"):
        await extract_claims(paper)


@pytest.mark.asyncio
async def test_decomposition_uses_flash_model(monkeypatch):
    requested_models = []

    class RecordingLLM:
        async def complete(self, **kwargs):
            requested_models.append(kwargs["model"])
            return json.dumps(
                {
                    "claims": [
                        {
                            "type": "procedure",
                            "specificity": "fully_described",
                            "cited_ref_ids": [],
                            "raw_text": "Cells were washed twice with PBS.",
                            "raw_sentence_id": 0,
                        }
                    ]
                }
            )

    monkeypatch.setattr(methods_extract, "get_llm", lambda: RecordingLLM())
    paper = Paper(
        paper_id="paper",
        source=PaperSource.UPLOAD,
        title="Paper",
        sections={
            "methods": Section(
                name="methods",
                text="[0] Cells were washed twice with PBS.",
            )
        },
    )

    await extract_claims(paper)

    assert requested_models == ["flash"]


@pytest.mark.asyncio
async def test_multiple_method_chunks_are_decomposed_concurrently(monkeypatch):
    active = 0
    peak_active = 0

    class ConcurrentLLM:
        async def complete(self, **kwargs):
            nonlocal active, peak_active
            active += 1
            peak_active = max(peak_active, active)
            await asyncio.sleep(0.01)
            prompt = kwargs["prompt"]
            sentence_id = 0 if "[0]" in prompt else 1
            text = (
                "Cells were washed twice with PBS."
                if sentence_id == 0
                else "Images were segmented using Tool X."
            )
            active -= 1
            return json.dumps(
                {
                    "claims": [
                        {
                            "type": "procedure",
                            "specificity": "fully_described",
                            "cited_ref_ids": [],
                            "raw_text": text,
                            "raw_sentence_id": sentence_id,
                        }
                    ]
                }
            )

    monkeypatch.setattr(methods_extract, "get_llm", lambda: ConcurrentLLM())
    monkeypatch.setattr(
        methods_extract,
        "_method_chunks",
        lambda _text, _max_chars: [
            "[0] Cells were washed twice with PBS.",
            "[1] Images were segmented using Tool X.",
        ],
    )
    paper = Paper(
        paper_id="paper",
        source=PaperSource.UPLOAD,
        title="Paper",
        sections={
            "methods": Section(
                name="methods",
                text="[0] Cells were washed twice with PBS.\n"
                "[1] Images were segmented using Tool X.",
            )
        },
    )

    claims = await extract_claims(paper)

    assert peak_active == 2
    assert [claim.raw_sentence_id for claim in claims] == [0, 1]


@pytest.mark.asyncio
async def test_timed_out_chunk_falls_back_to_rules(monkeypatch):
    class TimedOutLLM:
        async def complete(self, **kwargs):
            await asyncio.sleep(1)
            raise AssertionError("timeout should cancel the request")

    monkeypatch.setattr(methods_extract, "get_llm", lambda: TimedOutLLM())
    monkeypatch.setattr(
        methods_extract,
        "get_settings",
        lambda: Settings(
            app_max_methods_chunk_chars=1_000,
            app_llm_chunk_timeout_seconds=0.01,
            app_extraction_wall_budget_seconds=0.02,
        ),
    )
    paper = Paper(
        paper_id="paper",
        source=PaperSource.UPLOAD,
        title="Paper",
        sections={
            "methods": Section(
                name="methods",
                text="[0] Cells were washed twice with PBS.\n"
                "[1] Images were segmented using Tool X.",
            )
        },
    )

    claims = await extract_claims(paper)

    assert [claim.raw_sentence_id for claim in claims] == [0, 1]
    assert {claim.extraction_mode for claim in claims} == {"rules_llm_fallback"}


@pytest.mark.asyncio
async def test_provider_error_falls_back_to_rules(monkeypatch):
    class FailingLLM:
        async def complete(self, **_kwargs):
            raise OSError("provider unavailable")

    monkeypatch.setattr(methods_extract, "get_llm", lambda: FailingLLM())
    paper = Paper(
        paper_id="paper",
        source=PaperSource.UPLOAD,
        title="Paper",
        sections={
            "methods": Section(
                name="methods",
                text="[0] Cells were washed twice with PBS.",
            )
        },
    )

    claims = await extract_claims(paper)

    assert len(claims) == 1
    assert claims[0].extraction_mode == "rules_llm_fallback"


@pytest.mark.asyncio
async def test_chunk_fallback_preserves_successful_llm_chunks(monkeypatch):
    class PartiallyTimedOutLLM:
        async def complete(self, **kwargs):
            prompt = kwargs["prompt"]
            if "[1]" in prompt:
                await asyncio.sleep(1)
            return json.dumps(
                {
                    "claims": [
                        {
                            "type": "procedure",
                            "specificity": "fully_described",
                            "cited_ref_ids": [],
                            "raw_text": "Cells were washed twice with PBS.",
                            "raw_sentence_id": 0,
                        }
                    ]
                }
            )

    monkeypatch.setattr(methods_extract, "get_llm", lambda: PartiallyTimedOutLLM())
    monkeypatch.setattr(
        methods_extract,
        "_method_chunks",
        lambda _text, _max_chars: [
            "[0] Cells were washed twice with PBS.",
            "[1] Images were segmented using Tool X.",
        ],
    )
    monkeypatch.setattr(
        methods_extract,
        "get_settings",
        lambda: Settings(
            app_llm_chunk_timeout_seconds=0.01,
            app_extraction_wall_budget_seconds=0.1,
        ),
    )
    paper = Paper(
        paper_id="paper",
        source=PaperSource.UPLOAD,
        title="Paper",
        sections={
            "methods": Section(
                name="methods",
                text="[0] Cells were washed twice with PBS.\n"
                "[1] Images were segmented using Tool X.",
            )
        },
    )

    claims = await extract_claims(paper)

    assert [claim.extraction_mode for claim in claims] == [
        "llm",
        "rules_llm_fallback",
    ]


@pytest.mark.asyncio
async def test_large_paper_uses_rules_without_calling_llm(monkeypatch):
    class UnexpectedLLM:
        async def complete(self, **_kwargs):
            raise AssertionError("large-paper extraction must not call the LLM")

    monkeypatch.setattr(methods_extract, "get_llm", lambda: UnexpectedLLM())
    monkeypatch.setattr(
        methods_extract,
        "get_settings",
        lambda: Settings(
            app_methods_extraction_mode="hybrid",
            app_large_methods_sentence_threshold=2,
        ),
    )
    paper = Paper(
        paper_id="paper",
        source=PaperSource.UPLOAD,
        title="Large paper",
        sections={
            "methods": Section(
                name="methods",
                text="[0] Cells were washed twice with PBS.\n"
                "[1] Dissociation was performed as described previously [b12].",
            )
        },
    )

    claims = await extract_claims(paper)

    assert len(claims) == 2
    assert {claim.extraction_mode for claim in claims} == {"rules_large_paper"}
    assert claims[1].cited_ref_ids == ["b12"]
    assert claims[1].specificity.value == "shortcut_citation"


@pytest.mark.asyncio
async def test_rule_extraction_skips_heading_fragments(monkeypatch):
    monkeypatch.setattr(
        methods_extract,
        "get_settings",
        lambda: Settings(app_methods_extraction_mode="rules"),
    )
    paper = Paper(
        paper_id="paper",
        source=PaperSource.UPLOAD,
        title="Paper",
        sections={
            "methods": Section(
                name="methods",
                text="[0] Diff.\n[1] Cells were washed twice with PBS.",
            )
        },
    )

    claims = await extract_claims(paper)

    assert [claim.raw_sentence_id for claim in claims] == [1]
