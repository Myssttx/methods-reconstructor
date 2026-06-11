from __future__ import annotations
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    DECOMPOSING = "decomposing"
    RESOLVING = "resolving"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    FAILED = "failed"


class JobEvent(BaseModel):
    timestamp: str
    status: JobStatus
    message: str
    detail: dict[str, Any] | None = None


class Job(BaseModel):
    job_id: str
    paper_input: str
    status: JobStatus = JobStatus.PENDING
    events: list[JobEvent] = Field(default_factory=list)
    paper_id: str | None = None
    protocol_id: str | None = None
    error: str | None = None
    timings_ms: dict[str, float] = Field(default_factory=dict)
    started_at: str
    updated_at: str
    completed_at: str | None = None
