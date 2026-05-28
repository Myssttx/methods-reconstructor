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
    reproducibility_score: float
    section_scores: list[SectionScore] = Field(default_factory=list)
    sections: dict[str, list[Claim]] = Field(default_factory=dict)
    gaps: list[Gap] = Field(default_factory=list)
    generated_at: str
    version: str = "1.0.0"
