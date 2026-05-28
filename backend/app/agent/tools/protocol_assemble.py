"""Final assembly: claims → ReconstructedProtocol with scores + gap report."""

import json
import uuid
from datetime import datetime, timezone

from app.agent.prompts import PROTOCOL_ASSEMBLY_SYSTEM, PROTOCOL_ASSEMBLY_USER
from app.llm.gemini_client import get_llm
from app.logging import get_logger
from app.models import (
    Claim,
    ClaimType,
    Gap,
    Paper,
    ReconstructedProtocol,
    ResolutionStatus,
    SectionScore,
    Specificity,
)

log = get_logger(__name__)


CLAIM_WEIGHTS: dict[ClaimType, float] = {
    ClaimType.PROCEDURE: 3.0,
    ClaimType.SAMPLE_PREP: 3.0,
    ClaimType.ANALYSIS: 2.5,
    ClaimType.PARAMETER: 2.0,
    ClaimType.REAGENT: 1.5,
    ClaimType.EQUIPMENT: 1.0,
    ClaimType.SOFTWARE: 1.5,
    ClaimType.DATASET: 2.0,
}


def _resolution_factor(claim: Claim) -> float:
    if claim.specificity == Specificity.FULLY_DESCRIBED:
        return 0.7
    if claim.resolution_status == ResolutionStatus.RESOLVED:
        return 1.0 if claim.confidence >= 0.7 else 0.5
    if claim.resolution_status == ResolutionStatus.TERMINAL_GAP:
        return 0.0
    return 0.0


def compute_scores(claims: list[Claim]) -> tuple[float, list[SectionScore]]:
    if not claims:
        return 0.0, []

    total_weight = 0.0
    earned_weight = 0.0
    per_type_total: dict[ClaimType, float] = {}
    per_type_earned: dict[ClaimType, float] = {}
    per_type_count: dict[ClaimType, int] = {}
    per_type_resolved: dict[ClaimType, int] = {}

    for c in claims:
        w = CLAIM_WEIGHTS.get(c.type, 1.0)
        f = _resolution_factor(c)
        total_weight += w
        earned_weight += w * f
        per_type_total[c.type] = per_type_total.get(c.type, 0) + w
        per_type_earned[c.type] = per_type_earned.get(c.type, 0) + w * f
        per_type_count[c.type] = per_type_count.get(c.type, 0) + 1
        if c.resolution_status == ResolutionStatus.RESOLVED or c.specificity == Specificity.FULLY_DESCRIBED:
            per_type_resolved[c.type] = per_type_resolved.get(c.type, 0) + 1

    overall = 100.0 * earned_weight / total_weight if total_weight > 0 else 0.0
    section_scores = [
        SectionScore(
            section=t.value,
            score=100.0 * per_type_earned[t] / per_type_total[t] if per_type_total[t] > 0 else 0.0,
            n_claims=per_type_count[t],
            n_resolved=per_type_resolved.get(t, 0),
        )
        for t in per_type_total
    ]
    return round(overall, 1), section_scores


async def assemble(paper: Paper, claims: list[Claim], job_id: str) -> ReconstructedProtocol:
    claims_payload = json.dumps([c.model_dump(mode="json") for c in claims])

    user = PROTOCOL_ASSEMBLY_USER.format(
        paper_title=paper.title,
        paper_id=paper.paper_id,
        claims_json=claims_payload,
    )

    llm = get_llm()
    resp = await llm.complete(prompt=user, system=PROTOCOL_ASSEMBLY_SYSTEM, model="pro", response_format="json")
    try:
        data = json.loads(resp)
    except json.JSONDecodeError:
        log.warning("assemble.bad_json", preview=resp[:200])
        data = {"sections": {}, "gap_report": []}

    # Map text-only sections back into claim references so the UI can show provenance.
    claims_by_id = {c.claim_id: c for c in claims}
    sections_out: dict[str, list[Claim]] = {}
    for sec_name, items in (data.get("sections") or {}).items():
        sec_claims: list[Claim] = []
        for it in items:
            cid = it.get("claim_id")
            if cid in claims_by_id:
                sec_claims.append(claims_by_id[cid])
        if sec_claims:
            sections_out[sec_name] = sec_claims

    gaps = []
    for g in data.get("gap_report") or []:
        cid = g.get("claim_id")
        chain_trace = []
        if cid in claims_by_id:
            chain_trace = [step.model_dump() for step in claims_by_id[cid].resolution_chain]
        gaps.append(
            Gap(
                claim_id=cid or "",
                raw_text=g.get("raw_text", ""),
                reason=g.get("reason", ""),
                chain_trace=chain_trace,
                suggested_action=g.get("suggested_action", ""),
            )
        )

    score, section_scores = compute_scores(claims)

    return ReconstructedProtocol(
        protocol_id=str(uuid.uuid4()),
        job_id=job_id,
        source_paper_id=paper.paper_id,
        title=paper.title,
        reproducibility_score=score,
        section_scores=section_scores,
        sections=sections_out,
        gaps=gaps,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
