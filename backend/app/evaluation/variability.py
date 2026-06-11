from __future__ import annotations

from itertools import combinations
from statistics import mean, pstdev
from typing import Any


def claims_from_protocol(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for section_claims in (protocol.get("sections") or {}).values():
        claims.extend(section_claims)
    for gap in protocol.get("gaps") or []:
        claims.append(
            {
                "raw_text": gap.get("raw_text") or "",
                "type": gap.get("type") or "gap",
                "specificity": gap.get("specificity") or "terminal_gap",
                "resolution_status": "terminal_gap",
            }
        )
    return claims


def claim_signature(claim: dict[str, Any]) -> str:
    raw_text = " ".join(str(claim.get("raw_text") or "").casefold().split())
    return "|".join(
        [
            raw_text,
            str(claim.get("type") or ""),
            str(claim.get("specificity") or ""),
            str(claim.get("resolution_status") or ""),
        ]
    )


def signature_jaccard(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> float:
    left_signatures = {claim_signature(claim) for claim in left}
    right_signatures = {claim_signature(claim) for claim in right}
    union = left_signatures | right_signatures
    return len(left_signatures & right_signatures) / len(union) if union else 1.0


def label_agreement(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> float:
    def by_text(claims: list[dict[str, Any]]) -> dict[str, tuple[str, str, str]]:
        return {
            " ".join(str(claim.get("raw_text") or "").casefold().split()): (
                str(claim.get("type") or ""),
                str(claim.get("specificity") or ""),
                str(claim.get("resolution_status") or ""),
            )
            for claim in claims
            if claim.get("raw_text")
        }

    left_labels = by_text(left)
    right_labels = by_text(right)
    shared = set(left_labels) & set(right_labels)
    if not shared:
        return 0.0 if left_labels or right_labels else 1.0
    return sum(left_labels[text] == right_labels[text] for text in shared) / len(shared)


def variability_report(
    runs: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    counts = [len(run) for run in runs]
    pairs = list(combinations(runs, 2))
    jaccards = [signature_jaccard(left, right) for left, right in pairs]
    agreements = [label_agreement(left, right) for left, right in pairs]
    average_count = mean(counts) if counts else 0.0

    return {
        "n_runs": len(runs),
        "claim_counts": counts,
        "claim_count_mean": round(average_count, 3),
        "claim_count_min": min(counts) if counts else 0,
        "claim_count_max": max(counts) if counts else 0,
        "claim_count_cv": (
            round(pstdev(counts) / average_count, 4)
            if len(counts) > 1 and average_count
            else 0.0
        ),
        "pairwise_signature_jaccard_mean": (
            round(mean(jaccards), 4) if jaccards else 1.0
        ),
        "pairwise_signature_jaccard_min": (
            round(min(jaccards), 4) if jaccards else 1.0
        ),
        "pairwise_label_agreement_mean": (
            round(mean(agreements), 4) if agreements else 1.0
        ),
        "pairwise_label_agreement_min": (
            round(min(agreements), 4) if agreements else 1.0
        ),
    }
