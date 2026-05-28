"""Methods decomposition tool. Gemini 2.5 Pro (or offline mock)."""

import json
import uuid

from app.agent.prompts import METHODS_DECOMPOSITION_SYSTEM, METHODS_DECOMPOSITION_USER
from app.llm.gemini_client import get_llm
from app.logging import get_logger
from app.models import Claim, ClaimType, Paper, ResolutionStatus, Specificity

log = get_logger(__name__)


async def extract_claims(paper: Paper) -> list[Claim]:
    methods = paper.sections.get("methods")
    if methods is None or not methods.text.strip():
        log.info("methods_extract.empty", paper_id=paper.paper_id)
        return []

    refs_list = "\n".join(
        f"- {r.ref_id}: {r.raw_citation[:200]}" for r in paper.references[:50]
    )

    user_prompt = METHODS_DECOMPOSITION_USER.format(
        paper_id=paper.paper_id,
        title=paper.title,
        references_list=refs_list or "(none)",
        methods_text_with_sentence_ids=methods.text,
    )

    llm = get_llm()
    response = await llm.complete(
        prompt=user_prompt,
        system=METHODS_DECOMPOSITION_SYSTEM,
        model="pro",
        response_format="json",
    )

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        log.warning("methods_extract.bad_json", preview=response[:200])
        return []

    raw_claims = data.get("claims", [])
    claims: list[Claim] = []
    for raw in raw_claims:
        try:
            claims.append(
                Claim(
                    claim_id=str(uuid.uuid4()),
                    paper_id=paper.paper_id,
                    type=ClaimType(raw["type"]),
                    raw_text=raw["raw_text"],
                    raw_sentence_id=int(raw.get("raw_sentence_id", 0)),
                    specificity=Specificity(raw["specificity"]),
                    cited_ref_ids=list(raw.get("cited_ref_ids", [])),
                    resolution_status=(
                        ResolutionStatus.RESOLVED
                        if raw["specificity"] == "fully_described"
                        else ResolutionStatus.UNRESOLVED
                    ),
                    resolved_text=raw["raw_text"] if raw["specificity"] == "fully_described" else None,
                )
            )
        except (KeyError, ValueError) as e:
            log.warning("methods_extract.bad_claim", error=str(e), raw=raw)
            continue

    log.info("methods_extract.done", paper_id=paper.paper_id, n_claims=len(claims))
    return claims
