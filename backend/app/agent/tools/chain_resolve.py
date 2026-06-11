"""The recursive citation-chain resolver — the core IP.

For each unresolved claim:
  - If shortcut citation: fetch cited paper(s) → locate passage → if passage
    itself shortcuts, recurse (until depth cap).
  - If partially described: search the broader corpus for completions.
  - If standard_unspecified: search corpus for what "standard" means here.

Every call returns a ResolutionResult with a chain trace so the UI can show
the user *exactly* where the resolution came from (or where it broke).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from app.agent.schemas import ResolutionResult
from app.agent.tools.methods_locator import locate
from app.agent.tools.paper_fetch import FetchResult, fetch_by_ref
from app.config import get_settings
from app.llm.embeddings import aembed_text
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
    fetcher: Callable[[Reference | str], Awaitable[FetchResult]] | None = None,
) -> ResolutionResult:
    settings = get_settings()
    fetcher = fetcher or fetch_by_ref

    if depth >= settings.app_max_recursion_depth:
        return ResolutionResult(status="terminal_gap", terminal_reason=GapReason.DEPTH_EXCEEDED)

    if claim.specificity == Specificity.SHORTCUT_CITATION:
        return await _resolve_shortcut(
            claim,
            source_paper,
            on_event=on_event,
            depth=depth,
            chain=[],
            fetcher=fetcher,
        )

    if claim.specificity == Specificity.PARTIALLY_DESCRIBED:
        if claim.cited_ref_ids:
            cited_result = await _resolve_shortcut(
                claim,
                source_paper,
                on_event=on_event,
                depth=depth,
                chain=[],
                fetcher=fetcher,
            )
            if cited_result.status == "resolved":
                return cited_result
            corpus_result = await _resolve_partial(claim)
            return corpus_result if corpus_result.status == "inferred" else cited_result
        return await _resolve_partial(claim)

    if claim.specificity == Specificity.STANDARD_UNSPECIFIED:
        if claim.cited_ref_ids:
            cited_result = await _resolve_shortcut(
                claim,
                source_paper,
                on_event=on_event,
                depth=depth,
                chain=[],
                fetcher=fetcher,
            )
            if cited_result.status == "resolved":
                return cited_result
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
    fetcher: Callable[[Reference | str], Awaitable[FetchResult]],
) -> ResolutionResult:
    settings = get_settings()
    if depth >= settings.app_max_recursion_depth:
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

    refs_by_id = _reference_lookup(source_paper)
    fetched_any = False
    failure_reason = GapReason.REFERENCE_UNRESOLVED

    for ref_id in claim.cited_ref_ids:
        ref = refs_by_id.get(_normalize_ref_id(ref_id))
        if ref is None:
            continue

        if on_event:
            on_event(
                "chain.fetching",
                {"claim_id": claim.claim_id, "ref_id": ref_id, "depth": depth},
            )

        fetched = await fetcher(ref)
        ref_paper = fetched.paper
        if ref_paper is None:
            failure_reason = fetched.failure_reason or GapReason.SOURCE_UNAVAILABLE
            if on_event:
                on_event(
                    "chain.fetch_failed",
                    {"claim_id": claim.claim_id, "ref_id": ref_id, "depth": depth},
                )
            continue
        fetched_any = True

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
                chain=[*chain, step],
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
                chain=[*chain, step],
                fetcher=fetcher,
            )

        chain = [*chain, step]

    # No cited ref produced a resolution.
    fail_reason = GapReason.NO_MATCH_IN_CITED if fetched_any else failure_reason
    return ResolutionResult(status="terminal_gap", terminal_reason=fail_reason, chain=chain)


async def _resolve_partial(claim: Claim) -> ResolutionResult:
    """Try to augment a partially-described claim from the corpus of claims."""
    vec = await aembed_text(claim.raw_text)
    candidates = await hybrid_claim_search(
        claim.raw_text,
        vec,
        top_k=3,
        filters={"type": claim.type.value, "resolution_status": "resolved"},
        exclude_paper_id=claim.paper_id,
        exclude_paper_prefixes=("fixture:",),
    )
    candidates = [
        c
        for c in candidates
        if c.get("resolved_text")
        and _candidate_supports_claim(claim.raw_text, c)
    ]
    if not candidates:
        return ResolutionResult(status="terminal_gap", terminal_reason=GapReason.NO_MATCH_IN_CITED)
    top = candidates[0]
    return ResolutionResult(
        status="inferred",
        resolved_text=f"{claim.raw_text}\n\n[Corpus inference: {top['paper_id']}]\n{top['resolved_text']}",
        chain=[{"depth": 0, "source_paper_id": top["paper_id"], "sentence_ids": [], "extracted_text": top.get("resolved_text", "")}],
        confidence=0.5,
    )


async def _resolve_standard(claim: Claim) -> ResolutionResult:
    """For 'standard conditions' style claims, search the corpus for prevailing usage."""
    vec = await aembed_text(claim.raw_text)
    candidates = await hybrid_claim_search(
        claim.raw_text,
        vec,
        top_k=5,
        filters={"type": claim.type.value, "resolution_status": "resolved"},
        exclude_paper_id=claim.paper_id,
        exclude_paper_prefixes=("fixture:",),
    )
    candidates = [
        c
        for c in candidates
        if c.get("resolved_text")
        and _candidate_supports_claim(claim.raw_text, c)
    ]
    if not candidates:
        return ResolutionResult(status="terminal_gap", terminal_reason=GapReason.NO_MATCH_IN_CITED)
    top = candidates[0]
    return ResolutionResult(
        status="inferred",
        resolved_text=(
            f"{claim.raw_text}\n\n[Inferred 'standard' from corpus: {top['paper_id']}]\n{top['resolved_text']}"
        ),
        chain=[{"depth": 0, "source_paper_id": top["paper_id"], "sentence_ids": [], "extracted_text": top.get("resolved_text", "")}],
        confidence=0.4,
    )


def _normalize_ref_id(ref_id: str) -> str:
    """Normalize a ref id for lookup, preserving format to avoid collisions.

    Strips punctuation only — does NOT strip format prefixes like 'ref_' or 'b'
    so that ref_12 and b12 remain distinct keys.
    """
    return ref_id.strip().lower().strip("[]#")


def _reference_lookup(paper: Paper) -> dict[str, Reference]:
    return {_normalize_ref_id(ref.ref_id): ref for ref in paper.references}


def _has_meaningful_overlap(left: str, right: str) -> bool:
    stop = {
        "using",
        "with",
        "from",
        "were",
        "was",
        "that",
        "this",
        "following",
        "briefly",
        "standard",
        "above",
        "described",
        "used",
        "method",
        "methods",
        "cell",
        "cells",
        "tissue",
        "section",
        "sections",
        "sample",
        "samples",
        "human",
        "humans",
        "mouse",
        "mice",
        "tumor",
        "tumors",
        "tumour",
        "tumours",
        "hour",
        "hours",
        "minute",
        "minutes",
        "well",
        "wells",
        "plate",
        "plates",
    }
    left_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", left.casefold())
        if len(token) >= 4 and token not in stop
    }
    right_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", right.casefold())
        if len(token) >= 4 and token not in stop
    }
    shared = left_tokens & right_tokens
    return len(shared) >= 2 and len(shared) / max(1, min(len(left_tokens), len(right_tokens))) >= 0.2


def _candidate_supports_claim(claim_text: str, candidate: dict) -> bool:
    raw_text = str(candidate.get("raw_text") or "")
    resolved_text = str(candidate.get("resolved_text") or "")
    if not _has_meaningful_overlap(claim_text, raw_text):
        return False
    if resolved_text.strip() == raw_text.strip():
        return True
    return _has_meaningful_overlap(claim_text, resolved_text)
