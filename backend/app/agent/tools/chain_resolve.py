"""The recursive citation-chain resolver — the core IP.

For each unresolved claim:
  - If shortcut citation: fetch cited paper(s) → locate passage → if passage
    itself shortcuts, recurse (until depth cap).
  - If partially described: search the broader corpus for completions.
  - If standard_unspecified: search corpus for what "standard" means here.

Every call returns a ResolutionResult with a chain trace so the UI can show
the user *exactly* where the resolution came from (or where it broke).
"""

from typing import Callable

from app.agent.schemas import ResolutionResult
from app.agent.tools.methods_locator import locate
from app.agent.tools.paper_fetch import fetch_by_ref
from app.config import get_settings
from app.llm.embeddings import embed_text
from app.logging import get_logger
from app.models import Claim, GapReason, Paper, Reference, Specificity
from app.search.hybrid_search import hybrid_claim_search

log = get_logger(__name__)


async def resolve_claim(
    claim: Claim,
    source_paper: Paper,
    *,
    on_event: Callable[[str, dict], None] | None = None,
    depth: int = 0,
) -> ResolutionResult:
    settings = get_settings()

    if depth > settings.app_max_recursion_depth:
        return ResolutionResult(status="terminal_gap", terminal_reason=GapReason.DEPTH_EXCEEDED)

    if claim.specificity == Specificity.SHORTCUT_CITATION:
        return await _resolve_shortcut(
            claim, source_paper, on_event=on_event, depth=depth, chain=[]
        )

    if claim.specificity == Specificity.PARTIALLY_DESCRIBED:
        return await _resolve_partial(claim)

    if claim.specificity == Specificity.STANDARD_UNSPECIFIED:
        return await _resolve_standard(claim)

    return ResolutionResult(
        status="resolved",
        resolved_text=claim.raw_text,
        confidence=0.7,
    )


async def _resolve_shortcut(
    claim: Claim,
    source_paper: Paper,
    *,
    on_event: Callable[[str, dict], None] | None,
    depth: int,
    chain: list[dict],
) -> ResolutionResult:
    settings = get_settings()
    if depth > settings.app_max_recursion_depth:
        return ResolutionResult(
            status="terminal_gap",
            terminal_reason=GapReason.DEPTH_EXCEEDED,
            chain=chain,
        )

    if not claim.cited_ref_ids:
        return ResolutionResult(
            status="terminal_gap",
            terminal_reason=GapReason.NO_REFERENCE,
            chain=chain,
        )

    refs_by_id = {r.ref_id: r for r in source_paper.references}

    for ref_id in claim.cited_ref_ids:
        ref = refs_by_id.get(ref_id)
        if ref is None:
            continue

        if on_event:
            on_event(
                "chain.fetching",
                {"claim_id": claim.claim_id, "ref_id": ref_id, "depth": depth},
            )

        ref_paper = await fetch_by_ref(ref)
        if ref_paper is None:
            if on_event:
                on_event(
                    "chain.fetch_failed",
                    {"claim_id": claim.claim_id, "ref_id": ref_id, "depth": depth},
                )
            continue

        result = await locate(ref_paper, claim)

        step = {
            "depth": depth,
            "source_paper_id": ref_paper.paper_id,
            "sentence_ids": result.sentence_ids,
            "extracted_text": result.passage_text,
        }

        if result.fully_describes:
            return ResolutionResult(
                status="resolved",
                resolved_text=result.passage_text,
                chain=chain + [step],
                confidence=0.85 - 0.1 * depth,
            )

        if result.is_itself_shortcut and result.new_cited_refs:
            # Recurse: build a synthetic sub-claim that points at the new refs.
            sub_claim = claim.model_copy(
                update={
                    "raw_text": result.passage_text or claim.raw_text,
                    "cited_ref_ids": result.new_cited_refs,
                }
            )
            return await _resolve_shortcut(
                sub_claim,
                ref_paper,
                on_event=on_event,
                depth=depth + 1,
                chain=chain + [step],
            )

        chain = chain + [step]

    # No cited ref produced a resolution.
    fail_reason = (
        GapReason.PAYWALL_OR_DEAD
        if all((await fetch_by_ref(refs_by_id[rid]) is None) for rid in claim.cited_ref_ids if rid in refs_by_id)
        else GapReason.NO_MATCH_IN_CITED
    )
    return ResolutionResult(status="terminal_gap", terminal_reason=fail_reason, chain=chain)


async def _resolve_partial(claim: Claim) -> ResolutionResult:
    """Try to augment a partially-described claim from the corpus of claims."""
    vec = embed_text(claim.raw_text)
    candidates = await hybrid_claim_search(claim.raw_text, vec, top_k=3, filters={"type": claim.type.value})
    candidates = [c for c in candidates if c.get("claim_id") != claim.claim_id and c.get("resolved_text")]
    if not candidates:
        return ResolutionResult(status="terminal_gap", terminal_reason=GapReason.NO_MATCH_IN_CITED)
    top = candidates[0]
    return ResolutionResult(
        status="resolved",
        resolved_text=f"{claim.raw_text}\n\n[Augmented from corpus: {top['paper_id']}]\n{top['resolved_text']}",
        chain=[{"depth": 0, "source_paper_id": top["paper_id"], "sentence_ids": [], "extracted_text": top.get("resolved_text", "")}],
        confidence=0.5,
    )


async def _resolve_standard(claim: Claim) -> ResolutionResult:
    """For 'standard conditions' style claims, search the corpus for prevailing usage."""
    vec = embed_text(claim.raw_text)
    candidates = await hybrid_claim_search(claim.raw_text, vec, top_k=5, filters={"type": claim.type.value})
    candidates = [c for c in candidates if c.get("resolved_text")]
    if not candidates:
        return ResolutionResult(status="terminal_gap", terminal_reason=GapReason.NO_MATCH_IN_CITED)
    top = candidates[0]
    return ResolutionResult(
        status="resolved",
        resolved_text=(
            f"{claim.raw_text}\n\n[Inferred 'standard' from corpus: {top['paper_id']}]\n{top['resolved_text']}"
        ),
        chain=[{"depth": 0, "source_paper_id": top["paper_id"], "sentence_ids": [], "extracted_text": top.get("resolved_text", "")}],
        confidence=0.4,
    )
