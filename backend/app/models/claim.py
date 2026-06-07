from enum import Enum

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    REAGENT = "reagent"
    EQUIPMENT = "equipment"
    SAMPLE_PREP = "sample_prep"
    PROCEDURE = "procedure"
    ANALYSIS = "analysis"
    PARAMETER = "parameter"
    DATASET = "dataset"
    SOFTWARE = "software"


class Specificity(str, Enum):
    FULLY_DESCRIBED = "fully_described"
    PARTIALLY_DESCRIBED = "partially_described"
    SHORTCUT_CITATION = "shortcut_citation"
    STANDARD_UNSPECIFIED = "standard_unspecified"


class ResolutionStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    INFERRED = "inferred"
    TERMINAL_GAP = "terminal_gap"


class GapReason(str, Enum):
    DEPTH_EXCEEDED = "depth_exceeded"
    PAYWALL_OR_DEAD = "paywall_or_dead"
    SOURCE_UNAVAILABLE = "source_unavailable"
    REFERENCE_UNRESOLVED = "reference_unresolved"
    NO_MATCH_IN_CITED = "no_match_in_cited"
    NO_REFERENCE = "no_reference"
    PARSING_FAILED = "parsing_failed"


class ChainStep(BaseModel):
    depth: int
    source_paper_id: str
    sentence_ids: list[int] = Field(default_factory=list)
    extracted_text: str = ""


class Claim(BaseModel):
    claim_id: str
    paper_id: str
    type: ClaimType
    raw_text: str
    raw_sentence_id: int = 0
    specificity: Specificity
    cited_ref_ids: list[str] = Field(default_factory=list)
    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    resolved_text: str | None = None
    resolution_chain: list[ChainStep] = Field(default_factory=list)
    terminal_gap_reason: GapReason | None = None
    confidence: float = 0.0
