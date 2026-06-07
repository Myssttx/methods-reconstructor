"""Final assembly: claims → ReconstructedProtocol with scores + gap report."""

import json
import uuid
from datetime import UTC, datetime

from app.agent.prompts import PROTOCOL_ASSEMBLY_SYSTEM, PROTOCOL_ASSEMBLY_USER
from app.agent.schemas import AssemblyOutput
from app.config import get_settings
from app.llm.gemini_client import get_llm
from app.logging import get_logger
from app.models import (
    Claim,
    ClaimType,
    Gap,
    GapReason,
    Paper,
    ReconstructedProtocol,
    ResolutionStatus,
    SectionScore,
    Specificity,
)

log = get_logger(__name__)


def _resolution_factor(claim: Claim) -> float:
    if claim.specificity == Specificity.FULLY_DESCRIBED:
        return 1.0
    if claim.resolution_status == ResolutionStatus.RESOLVED:
        has_sentence_evidence = any(step.sentence_ids for step in claim.resolution_chain)
        return 1.0 if has_sentence_evidence else 0.0
    return 0.0


def compute_scores(claims: list[Claim]) -> tuple[float, list[SectionScore]]:
    if not claims:
        return 0.0, []

    total = 0
    earned = 0.0
    per_type_total: dict[ClaimType, int] = {}
    per_type_earned: dict[ClaimType, float] = {}
    per_type_count: dict[ClaimType, int] = {}
    per_type_resolved: dict[ClaimType, int] = {}

    for c in claims:
        f = _resolution_factor(c)
        total += 1
        earned += f
        per_type_total[c.type] = per_type_total.get(c.type, 0) + 1
        per_type_earned[c.type] = per_type_earned.get(c.type, 0) + f
        per_type_count[c.type] = per_type_count.get(c.type, 0) + 1
        if f == 1.0:
            per_type_resolved[c.type] = per_type_resolved.get(c.type, 0) + 1

    overall = 100.0 * earned / total if total else 0.0
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
    settings = get_settings()
    data = AssemblyOutput()
    if len(claims_payload) <= settings.app_max_assembly_chars:
        user = PROTOCOL_ASSEMBLY_USER.format(
            paper_title=paper.title,
            paper_id=paper.paper_id,
            claims_json=claims_payload,
        )
        llm = get_llm()
        resp = await llm.complete(
            prompt=user,
            system=PROTOCOL_ASSEMBLY_SYSTEM,
            model="pro",
            response_format="json",
        )
        try:
            data = AssemblyOutput.model_validate(json.loads(resp))
        except (json.JSONDecodeError, ValueError):
            log.warning("assemble.bad_json", preview=resp[:200])
    else:
        log.info("assemble.deterministic", payload_chars=len(claims_payload))

    claims_by_id = {c.claim_id: c for c in claims}
    eligible_ids = {
        c.claim_id
        for c in claims
        if c.resolution_status != ResolutionStatus.TERMINAL_GAP
    }
    sections_out: dict[str, list[Claim]] = {}
    assigned: set[str] = set()
    for sec_name, items in data.sections.items():
        sec_claims: list[Claim] = []
        for it in items:
            cid = it.claim_id
            if cid in eligible_ids and cid not in assigned:
                sec_claims.append(claims_by_id[cid])
                assigned.add(cid)
        if sec_claims:
            sections_out[sec_name] = sec_claims

    for claim in claims:
        if claim.claim_id not in eligible_ids or claim.claim_id in assigned:
            continue
        sections_out.setdefault(_section_for_claim(claim), []).append(claim)
        assigned.add(claim.claim_id)

    gaps: list[Gap] = []
    for claim in claims:
        if claim.resolution_status != ResolutionStatus.TERMINAL_GAP:
            continue
        reason = claim.terminal_gap_reason or GapReason.PARSING_FAILED
        gaps.append(
            Gap(
                claim_id=claim.claim_id,
                raw_text=claim.raw_text,
                reason=reason.value,
                chain_trace=[step.model_dump() for step in claim.resolution_chain],
                suggested_action=_suggest_action(reason),
            )
        )

    score, section_scores = compute_scores(claims)

    return ReconstructedProtocol(
        protocol_id=str(uuid.uuid4()),
        job_id=job_id,
        source_paper_id=paper.paper_id,
        title=paper.title,
        methods_evidence_score=score,
        reproducibility_score=score,
        section_scores=section_scores,
        sections=sections_out,
        gaps=gaps,
        generated_at=datetime.now(UTC).isoformat(),
    )


def _section_for_claim(claim: Claim) -> str:
    return {
        "reagent": "reagents",
        "equipment": "equipment",
        "sample_prep": "sample_prep",
        "procedure": "procedure",
        "analysis": "analysis",
        "parameter": "software",
        "software": "software",
        "dataset": "datasets",
    }[claim.type.value]


def _suggest_action(reason: GapReason) -> str:
    if reason == GapReason.DEPTH_EXCEEDED:
        return "Inspect the final citation-chain step manually."
    if reason == GapReason.SOURCE_UNAVAILABLE:
        return "Locate an accessible full-text copy or request the protocol from the authors."
    if reason == GapReason.REFERENCE_UNRESOLVED:
        return "Resolve the bibliography entry to a DOI or stable paper identifier."
    if reason == GapReason.NO_MATCH_IN_CITED:
        return "Review the cited paper manually; retrieved methods passages did not support the claim."
    if reason == GapReason.NO_REFERENCE:
        return "The source gives no traceable reference; contact the authors for procedural detail."
    return "Inspect the source document and extraction manually."
