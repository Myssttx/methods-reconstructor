"""Pydantic shapes the agent uses internally for tool I/O."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models import Claim, GapReason


class LocatorResult(BaseModel):
    fully_describes: bool
    is_itself_shortcut: bool
    new_cited_refs: list[str] = Field(default_factory=list)
    passage_text: str = ""
    sentence_ids: list[int] = Field(default_factory=list)


class ResolutionResult(BaseModel):
    status: Literal["resolved", "terminal_gap"]
    resolved_text: str | None = None
    chain: list[dict] = Field(default_factory=list)
    terminal_reason: GapReason | None = None
    confidence: float = 0.0


class AgentEvent(BaseModel):
    type: str
    timestamp: str
    data: dict
