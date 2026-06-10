"""Sanity-check the deterministic OfflineLLM that powers offline demos + tests."""

import asyncio
import json

import pytest

from app.llm.gemini_client import OfflineLLM


@pytest.fixture
def llm():
    return OfflineLLM()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.mark.asyncio
async def test_decompose_classifies_shortcut(llm):
    prompt = (
        "Methods section:\n"
        "[0] Cells were maintained as described in Smith et al. 2019 [ref_3].\n"
        "[1] Centrifuged at 200g for 6 minutes at room temperature.\n\n"
        "OUTPUT FORMAT: JSON.\n"
    )
    out = await llm.complete(prompt=prompt)
    data = json.loads(out)
    claims = data["claims"]
    assert len(claims) == 2
    assert claims[0]["specificity"] == "shortcut_citation"
    assert "ref_3" in claims[0]["cited_ref_ids"]
    assert claims[1]["specificity"] == "fully_described"


@pytest.mark.asyncio
async def test_decompose_preserves_grobid_reference_ids(llm):
    prompt = (
        "Methods section:\n"
        "[0] Images were segmented as described previously [b27].\n\n"
        "OUTPUT FORMAT: JSON.\n"
    )
    out = await llm.complete(prompt=prompt)
    claims = json.loads(out)["claims"]
    assert claims[0]["cited_ref_ids"] == ["b27"]


@pytest.mark.asyncio
async def test_decompose_classifies_standard(llm):
    prompt = "Methods section:\n[0] Mice were housed under standard conditions.\n\nOUTPUT FORMAT: JSON."
    out = await llm.complete(prompt=prompt)
    claims = json.loads(out)["claims"]
    assert claims[0]["specificity"] == "standard_unspecified"


@pytest.mark.asyncio
async def test_locator_detects_shortcut(llm):
    prompt = (
        "<ORIGINAL_CLAIM>\nCells were dissociated.\n</ORIGINAL_CLAIM>\n\n"
        '<CANDIDATE_PASSAGE source="X">\n'
        "Tissue was dissociated as previously described in Okamoto et al. 2016 [ref_1].\n"
        "</CANDIDATE_PASSAGE>"
    )
    out = await llm.complete(prompt=prompt)
    data = json.loads(out)
    assert data["is_itself_shortcut"] is True
    assert "ref_1" in data["new_cited_refs"]
