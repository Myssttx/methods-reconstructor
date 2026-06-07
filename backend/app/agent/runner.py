"""Top-level agent orchestrator.

Streams `AgentEvent`s as it works. The API layer turns those events into SSE
messages for the frontend. Job + protocol state is persisted via the JobStore
(local file in dev, Firestore in cloud).
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from app.agent.schemas import AgentEvent
from app.agent.tools.chain_resolve import resolve_claim
from app.agent.tools.methods_extract import extract_claims
from app.agent.tools.protocol_assemble import assemble
from app.config import get_settings
from app.ingest.pipeline import ingest_identifier
from app.llm.budget import token_budget
from app.llm.embeddings import aembed_texts
from app.logging import get_logger
from app.models import (
    Claim,
    Job,
    JobEvent,
    JobStatus,
    ResolutionStatus,
    Specificity,
)
from app.search.claims_dao import bulk_index_claims, delete_claims_for_paper
from app.search.indexes import ensure_indexes
from app.storage.firestore_client import get_store

log = get_logger(__name__)


class JobCapacityError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


class AgentRunner:
    def __init__(self, job_id: str, identifier: str) -> None:
        self.job_id = job_id
        self.identifier = identifier
        self._history: list[AgentEvent] = []
        self._subscribers: set[asyncio.Queue[AgentEvent | None]] = set()
        self._done = False
        self.store = get_store()

    async def _emit(self, event_type: str, data: dict) -> None:
        self._publish(AgentEvent(type=event_type, timestamp=_now(), data=data))

    def _emit_sync(self, event_type: str, data: dict) -> None:
        """Sync version for callbacks from inside tool code."""
        self._publish(AgentEvent(type=event_type, timestamp=_now(), data=data))

    def _publish(self, event: AgentEvent) -> None:
        self._history.append(event)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("emit.queue_full", event_type=event.type)

    async def run(self) -> None:
        """Background-friendly entry point. Emits events; stores final protocol."""
        job = Job(
            job_id=self.job_id,
            paper_input=self.identifier,
            status=JobStatus.PENDING,
            started_at=_now(),
            updated_at=_now(),
        )
        try:
            await self.store.put_job(job.model_dump(mode="json"))
            settings = get_settings()
            with token_budget(settings.app_per_paper_token_budget):
                try:
                    async with asyncio.timeout(settings.app_agent_timeout_seconds):
                        await ensure_indexes()
                        await self._run_inner(job)
                except TimeoutError as e:
                    raise RuntimeError(
                        f"Reconstruction exceeded {settings.app_agent_timeout_seconds} seconds"
                    ) from e
        except Exception as e:
            log.exception("runner.failed", error=str(e))
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.updated_at = _now()
            await self.store.put_job(job.model_dump(mode="json"))
            await self._emit("error", {"message": str(e)})
        finally:
            self._done = True
            for queue in list(self._subscribers):
                queue.put_nowait(None)

    async def _run_inner(self, job: Job) -> None:
        await self._set_status(job, JobStatus.INGESTING, "Resolving paper identifier")

        paper = await ingest_identifier(self.identifier)
        if paper is None:
            raise RuntimeError(f"Could not resolve identifier: {self.identifier}")
        if not paper.methods_text().strip():
            raise RuntimeError(
                "The paper was resolved, but no methods full text could be extracted"
            )

        job.paper_id = paper.paper_id
        await self._emit("ingest", {
            "paper_id": paper.paper_id,
            "title": paper.title,
            "n_references": len(paper.references),
            "has_methods": bool(paper.methods_text()),
        })

        await self._set_status(job, JobStatus.DECOMPOSING, "Decomposing methods section into claims")
        claims = await extract_claims(paper)

        # Index claims (with embeddings) before resolution so the corpus is
        # immediately searchable.
        embeddings = await aembed_texts([c.raw_text for c in claims])
        await delete_claims_for_paper(paper.paper_id)
        await bulk_index_claims(claims, embeddings=embeddings)

        await self._emit("decompose", {
            "n_claims": len(claims),
            "by_specificity": _count_by_specificity(claims),
        })

        await self._set_status(job, JobStatus.RESOLVING, f"Resolving {len(claims)} claims")

        settings = get_settings()
        semaphore = asyncio.Semaphore(settings.app_max_concurrent_claims)

        async def resolve_one(claim: Claim) -> None:
            if claim.specificity == Specificity.FULLY_DESCRIBED:
                return
            async with semaphore:
                claim.resolution_status = ResolutionStatus.RESOLVING
                result = await resolve_claim(
                    claim,
                    paper,
                    on_event=lambda t, d: self._emit_sync(t, d),
                )

                if result.status in {"resolved", "inferred"}:
                    claim.resolution_status = (
                        ResolutionStatus.RESOLVED
                        if result.status == "resolved"
                        else ResolutionStatus.INFERRED
                    )
                    claim.resolved_text = result.resolved_text
                    claim.confidence = result.confidence
                    claim.resolution_chain = [
                        self._step_from_dict(s) for s in result.chain
                    ]
                else:
                    claim.resolution_status = ResolutionStatus.TERMINAL_GAP
                    claim.terminal_gap_reason = result.terminal_reason
                    claim.resolution_chain = [
                        self._step_from_dict(s) for s in result.chain
                    ]

                await self._emit("claim_resolved", {
                    "claim_id": claim.claim_id,
                    "status": claim.resolution_status.value,
                    "specificity": claim.specificity.value,
                    "type": claim.type.value,
                    "raw_text": claim.raw_text[:200],
                    "chain_depth": len(claim.resolution_chain),
                    "terminal_reason": (
                        claim.terminal_gap_reason.value if claim.terminal_gap_reason else None
                    ),
                })

        await asyncio.gather(*(resolve_one(claim) for claim in claims))
        await bulk_index_claims(claims, embeddings=embeddings)

        await self._set_status(job, JobStatus.ASSEMBLING, "Assembling reconstructed protocol")
        protocol = await assemble(paper, claims, job_id=self.job_id)
        await self.store.put_reconstruction(protocol.model_dump(mode="json"))
        job.protocol_id = protocol.protocol_id

        await self._emit("assemble", {
            "protocol_id": protocol.protocol_id,
            "score": protocol.methods_evidence_score,
            "section_scores": [s.model_dump() for s in protocol.section_scores],
            "n_gaps": len(protocol.gaps),
        })

        job.status = JobStatus.COMPLETE
        job.completed_at = _now()
        job.updated_at = _now()
        await self.store.put_job(job.model_dump(mode="json"))
        await self._emit("complete", {"protocol_id": protocol.protocol_id})

    @staticmethod
    def _step_from_dict(s: dict):
        from app.models import ChainStep

        return ChainStep(
            depth=int(s.get("depth", 0)),
            source_paper_id=s.get("source_paper_id", ""),
            sentence_ids=list(s.get("sentence_ids", [])),
            extracted_text=s.get("extracted_text", ""),
        )

    async def _set_status(self, job: Job, status: JobStatus, message: str) -> None:
        job.status = status
        job.events.append(JobEvent(timestamp=_now(), status=status, message=message))
        job.updated_at = _now()
        await self.store.put_job(job.model_dump(mode="json"))
        await self._emit("status", {"status": status.value, "message": message})

    async def stream(self) -> AsyncIterator[AgentEvent]:
        queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
        self._subscribers.add(queue)
        history = list(self._history)
        done = self._done
        try:
            for event in history:
                yield event
            if done:
                return
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield event
        finally:
            self._subscribers.discard(queue)


def _count_by_specificity(claims: list[Claim]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in claims:
        out[c.specificity.value] = out.get(c.specificity.value, 0) + 1
    return out


# Job registry — keep AgentRunner instances alive across API calls so the SSE
# stream endpoint can attach to an in-flight job.
_runners: dict[str, AgentRunner] = {}
_runner_tasks: dict[str, asyncio.Task[None]] = {}


def start_job(identifier: str) -> AgentRunner:
    settings = get_settings()
    if len(_runner_tasks) >= settings.app_max_concurrent_jobs:
        raise JobCapacityError(
            f"At most {settings.app_max_concurrent_jobs} reconstructions may run concurrently"
        )
    job_id = str(uuid.uuid4())
    runner = AgentRunner(job_id=job_id, identifier=identifier)
    _runners[job_id] = runner
    task = asyncio.create_task(runner.run())
    _runner_tasks[job_id] = task

    def cleanup(_task: asyncio.Task[None]) -> None:
        _runner_tasks.pop(job_id, None)
        _runners.pop(job_id, None)

    task.add_done_callback(cleanup)
    return runner


def get_runner(job_id: str) -> AgentRunner | None:
    return _runners.get(job_id)
