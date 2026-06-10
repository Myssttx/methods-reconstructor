import uuid

import pytest

from app.agent.tools import protocol_assemble
from app.agent.tools.protocol_assemble import compute_scores
from app.config import Settings
from app.models import (
    ChainStep,
    Claim,
    ClaimType,
    Paper,
    PaperSource,
    ResolutionStatus,
    Specificity,
)


def _c(type_: ClaimType, status: ResolutionStatus, spec=Specificity.SHORTCUT_CITATION, conf=1.0):
    claim = Claim(
        claim_id=str(uuid.uuid4()),
        paper_id="p",
        type=type_,
        raw_text="x",
        specificity=spec,
        resolution_status=status,
        confidence=conf,
    )
    if status == ResolutionStatus.RESOLVED and spec != Specificity.FULLY_DESCRIBED:
        claim.resolution_chain = [
            ChainStep(
                depth=0,
                source_paper_id="doi:10.1000/source",
                sentence_ids=[1, 2],
                extracted_text="evidence",
            )
        ]
    return claim


def test_score_all_resolved_high():
    claims = [
        _c(ClaimType.PROCEDURE, ResolutionStatus.RESOLVED),
        _c(ClaimType.REAGENT, ResolutionStatus.RESOLVED),
    ]
    overall, breakdown = compute_scores(claims)
    assert overall == 100.0
    assert len(breakdown) == 2


def test_score_all_terminal_gaps_zero():
    claims = [
        _c(ClaimType.PROCEDURE, ResolutionStatus.TERMINAL_GAP),
        _c(ClaimType.SAMPLE_PREP, ResolutionStatus.TERMINAL_GAP),
    ]
    overall, _ = compute_scores(claims)
    assert overall == 0.0


def test_score_fully_described_counts_as_source_evidence():
    claims = [
        _c(
            ClaimType.PROCEDURE,
            ResolutionStatus.RESOLVED,
            spec=Specificity.FULLY_DESCRIBED,
        )
    ]
    overall, _ = compute_scores(claims)
    assert overall == 100.0


def test_score_is_equal_claim_evidence_coverage():
    claims = [
        _c(ClaimType.PROCEDURE, ResolutionStatus.RESOLVED),
        _c(ClaimType.EQUIPMENT, ResolutionStatus.TERMINAL_GAP),
    ]
    overall, _ = compute_scores(claims)
    assert overall == 50.0


def test_corpus_inference_does_not_count_as_evidence():
    claims = [
        _c(ClaimType.PROCEDURE, ResolutionStatus.INFERRED),
        _c(
            ClaimType.REAGENT,
            ResolutionStatus.RESOLVED,
            spec=Specificity.FULLY_DESCRIBED,
        ),
    ]
    overall, _ = compute_scores(claims)
    assert overall == 50.0


@pytest.mark.asyncio
async def test_default_assembly_is_deterministic_and_does_not_call_llm(monkeypatch):
    monkeypatch.setattr(
        protocol_assemble,
        "get_settings",
        lambda: Settings(app_use_llm_assembly=False),
    )

    def unexpected_llm():
        raise AssertionError("LLM assembly should be disabled by default")

    monkeypatch.setattr(protocol_assemble, "get_llm", unexpected_llm)
    claim = _c(
        ClaimType.PROCEDURE,
        ResolutionStatus.RESOLVED,
        spec=Specificity.FULLY_DESCRIBED,
    )

    protocol = await protocol_assemble.assemble(
        Paper(
            paper_id="paper",
            source=PaperSource.UPLOAD,
            title="Paper",
        ),
        [claim],
        job_id="job",
    )

    assert protocol.sections["procedure"] == [claim]
    assert protocol.generation_metadata["assembly_mode"] == "deterministic"
