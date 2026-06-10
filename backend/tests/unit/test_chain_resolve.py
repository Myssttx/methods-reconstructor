import pytest

from app.agent.schemas import ResolutionResult
from app.agent.tools import chain_resolve
from app.agent.tools.paper_fetch import FetchResult
from app.models import (
    Claim,
    ClaimType,
    GapReason,
    Paper,
    PaperSource,
    Reference,
    Specificity,
)


@pytest.mark.asyncio
async def test_unavailable_shortcut_reference_returns_source_gap(monkeypatch):
    claim = Claim(
        claim_id="claim-1",
        paper_id="paper-1",
        type=ClaimType.PROCEDURE,
        raw_text="The procedure followed prior work [b24].",
        specificity=Specificity.SHORTCUT_CITATION,
        cited_ref_ids=["b24"],
    )
    paper = Paper(
        paper_id="paper-1",
        source=PaperSource.UPLOAD,
        title="Source paper",
        references=[
            Reference(
                ref_id="b24",
                raw_citation="Prior work",
                doi="10.1000/unavailable",
            )
        ],
    )

    async def unavailable(_ref):
        return FetchResult(paper=None, failure_reason=GapReason.SOURCE_UNAVAILABLE)

    monkeypatch.setattr(chain_resolve, "fetch_by_ref", unavailable)
    result = await chain_resolve.resolve_claim(claim, paper)

    assert result.status == "terminal_gap"
    assert result.terminal_reason == GapReason.SOURCE_UNAVAILABLE


@pytest.mark.asyncio
async def test_partial_claim_uses_other_papers_only_and_stays_inferred(monkeypatch):
    claim = Claim(
        claim_id="claim-2",
        paper_id="paper-source",
        type=ClaimType.PROCEDURE,
        raw_text="Cells were washed twice.",
        specificity=Specificity.PARTIALLY_DESCRIBED,
    )
    captured = {}

    async def fake_embed(_text):
        return [0.0]

    async def fake_search(_text, _vec, **kwargs):
        captured.update(kwargs)
        return [
                {
                    "claim_id": "candidate",
                    "paper_id": "paper-other",
                    "raw_text": "Cells were washed twice with PBS.",
                    "resolved_text": "Cells were washed twice with PBS.",
                }
        ]

    monkeypatch.setattr(chain_resolve, "aembed_text", fake_embed)
    monkeypatch.setattr(chain_resolve, "hybrid_claim_search", fake_search)

    result = await chain_resolve.resolve_claim(
        claim,
        Paper(
            paper_id="paper-source",
            source=PaperSource.UPLOAD,
            title="Source",
        ),
    )

    assert result.status == "inferred"
    assert captured["exclude_paper_id"] == "paper-source"
    assert captured["exclude_paper_prefixes"] == ("fixture:",)
    assert captured["filters"]["resolution_status"] == "resolved"


def test_reference_ids_are_normalized_across_grobid_and_llm_formats():
    paper = Paper(
        paper_id="paper",
        source=PaperSource.UPLOAD,
        title="Paper",
        references=[
            Reference(ref_id="b24", raw_citation="Prior paper B"),
            Reference(ref_id="ref_24", raw_citation="Prior paper Ref"),
        ],
    )
    lookup = chain_resolve._reference_lookup(paper)
    # M-5 fix: b24 and ref_24 must stay as distinct keys to avoid silent collisions.
    assert lookup[chain_resolve._normalize_ref_id("b24")].ref_id == "b24"
    assert lookup[chain_resolve._normalize_ref_id("ref_24")].ref_id == "ref_24"
    assert chain_resolve._normalize_ref_id("[b24]") == "b24"
    assert chain_resolve._normalize_ref_id("[ref_24]") == "ref_24"


def test_corpus_inference_requires_method_specific_overlap():
    assert chain_resolve._has_meaningful_overlap(
        "Cells were segmented into tumor and stroma masks.",
        "Tumor cells were segmented into object masks.",
    )
    assert not chain_resolve._has_meaningful_overlap(
        "Cells were segmented with Ilastik and CellProfiler.",
        "Reads were aligned to the mouse genome with STAR.",
    )
    assert not chain_resolve._has_meaningful_overlap(
        "The above described antibody panel was used to stain tissue sections.",
        "Cortical tissue was dissociated into single-cell suspensions as described.",
    )
    assert not chain_resolve._has_meaningful_overlap(
        "SCC9 cells in 24-well plates were infected for 36 hours.",
        "Sorted cells were incubated for 3 hours in 96-well plates.",
    )
    assert not chain_resolve._has_meaningful_overlap(
        "Human tumor samples were dissociated per manufacturer guidelines.",
        "Human samples and mouse models.",
    )


def test_corpus_inference_requires_resolved_evidence_to_match():
    claim_text = "Cells were segmented into tumor and stroma masks."
    assert chain_resolve._candidate_supports_claim(
        claim_text,
        {
            "raw_text": "Tumor cells were segmented into object masks.",
            "resolved_text": "Object masks were segmented with CellProfiler.",
        },
    )
    assert not chain_resolve._candidate_supports_claim(
        claim_text,
        {
            "raw_text": "Tumor cells were segmented into object masks.",
            "resolved_text": "Sorted cells were incubated with peptide.",
        },
    )


@pytest.mark.asyncio
async def test_partial_claim_prefers_explicit_citation_chain(monkeypatch):
    claim = Claim(
        claim_id="partial-cited",
        paper_id="source",
        type=ClaimType.PROCEDURE,
        raw_text="Cells were briefly segmented [b1].",
        specificity=Specificity.PARTIALLY_DESCRIBED,
        cited_ref_ids=["b1"],
    )
    paper = Paper(
        paper_id="source",
        source=PaperSource.UPLOAD,
        title="Source",
    )
    corpus_called = False

    async def cited(*_args, **_kwargs):
        return ResolutionResult(
            status="resolved",
            resolved_text="Cited procedure",
            chain=[
                {
                    "depth": 0,
                    "source_paper_id": "cited",
                    "sentence_ids": [1],
                    "extracted_text": "Cited procedure",
                }
            ],
            confidence=0.8,
        )

    async def corpus(_claim):
        nonlocal corpus_called
        corpus_called = True
        return ResolutionResult(status="terminal_gap", terminal_reason=GapReason.NO_MATCH_IN_CITED)

    monkeypatch.setattr(chain_resolve, "_resolve_shortcut", cited)
    monkeypatch.setattr(chain_resolve, "_resolve_partial", corpus)

    result = await chain_resolve.resolve_claim(claim, paper)

    assert result.status == "resolved"
    assert not corpus_called
