import uuid

from app.agent.tools.protocol_assemble import compute_scores
from app.models import Claim, ClaimType, ResolutionStatus, Specificity


def _c(type_: ClaimType, status: ResolutionStatus, spec=Specificity.SHORTCUT_CITATION, conf=1.0):
    return Claim(
        claim_id=str(uuid.uuid4()),
        paper_id="p",
        type=type_,
        raw_text="x",
        specificity=spec,
        resolution_status=status,
        confidence=conf,
    )


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


def test_score_partial_credit_for_fully_described():
    claims = [
        _c(
            ClaimType.PROCEDURE,
            ResolutionStatus.RESOLVED,
            spec=Specificity.FULLY_DESCRIBED,
        )
    ]
    overall, _ = compute_scores(claims)
    assert overall == 70.0


def test_score_weights_procedure_higher_than_equipment():
    """Procedure (weight 3.0) should swamp equipment (weight 1.0) in mixed claims."""
    claims = [
        _c(ClaimType.PROCEDURE, ResolutionStatus.RESOLVED),
        _c(ClaimType.EQUIPMENT, ResolutionStatus.TERMINAL_GAP),
    ]
    overall, _ = compute_scores(claims)
    # earned 3.0, total 4.0 → 75%
    assert overall == 75.0
