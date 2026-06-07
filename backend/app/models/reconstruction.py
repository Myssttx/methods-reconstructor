from typing import Any

from pydantic import BaseModel, Field

from app.models.claim import Claim


class SectionScore(BaseModel):
    section: str
    score: float
    n_claims: int
    n_resolved: int


class Gap(BaseModel):
    claim_id: str
    raw_text: str
    reason: str
    chain_trace: list[dict[str, Any]] = Field(default_factory=list)
    suggested_action: str


class ReconstructedProtocol(BaseModel):
    protocol_id: str
    job_id: str
    source_paper_id: str
    title: str
    methods_evidence_score: float
    # Kept for API compatibility. This is not a validated reproducibility measure.
    reproducibility_score: float
    score_methodology: str = (
        "Percentage of extracted methodological claims backed by source-paper text "
        "or sentence-level evidence from a cited paper. Corpus inferences do not count."
    )
    section_scores: list[SectionScore] = Field(default_factory=list)
    sections: dict[str, list[Claim]] = Field(default_factory=dict)
    gaps: list[Gap] = Field(default_factory=list)
    generated_at: str
    version: str = "1.0.0"
