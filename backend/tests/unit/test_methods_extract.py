import json

import pytest

from app.agent.tools import methods_extract
from app.agent.tools.methods_extract import extract_claims
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
