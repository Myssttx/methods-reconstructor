from __future__ import annotations
"""Pydantic shapes the agent uses internally for tool I/O."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models import ClaimType, GapReason, Specificity


class ExtractedClaim(BaseModel):
    type: ClaimType
    specificity: Specificity
    cited_ref_ids: list[str] = Field(default_factory=list)
    raw_text: str
    raw_sentence_id: int


class DecompositionOutput(BaseModel):
    claims: list[ExtractedClaim]


class LocatorDecision(BaseModel):
    fully_describes: bool = False
    is_itself_shortcut: bool = False
    new_cited_refs: list[str] = Field(default_factory=list)


class AssemblyItem(BaseModel):
    claim_id: str
    text: str = ""


class AssemblyOutput(BaseModel):
    sections: dict[str, list[AssemblyItem]] = Field(default_factory=dict)


class LocatorResult(BaseModel):
    fully_describes: bool
    is_itself_shortcut: bool
    new_cited_refs: list[str] = Field(default_factory=list)
    passage_text: str = ""
    sentence_ids: list[int] = Field(default_factory=list)


class ResolutionResult(BaseModel):
    status: Literal["resolved", "inferred", "terminal_gap"]
    resolved_text: str | None = None
    chain: list[dict] = Field(default_factory=list)
    terminal_reason: GapReason | None = None
    confidence: float = 0.0


class AgentEvent(BaseModel):
    type: str
    timestamp: str
    data: dict
