"""Top-level agent orchestrator.

Streams `AgentEvent`s as it works. The API layer turns those events into SSE
messages for the frontend. Job + protocol state is persisted via the JobStore
(local file in dev, Firestore in cloud).
"""

import asyncio
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import time

from app.agent.schemas import AgentEvent
from app.agent.tools.chain_resolve import resolve_claim
from app.agent.tools.methods_extract import extract_claims
from app.agent.tools.paper_fetch import PaperFetchSession
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
    Paper,
    ResolutionStatus,
    Specificity,
)
from app.search.claims_dao import (
    bulk_index_claims,
    claims_for_paper,
    delete_claims_for_paper,
)
from app.search.indexes import ensure_indexes
from app.storage.firestore_client import get_store

log = get_logger(__name__)


class JobCapacityError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _error_message(error: Exception) -> str:
    return str(error).strip() or type(error).__name__


class AgentRunner:
    def __init__(
        self,
        job_id: str,
        identifier: str,
        *,
        reuse_cached_claims: bool | None = None,
    ) -> None:
        self.job_id = job_id
        self.identifier = identifier
        self._history: list[AgentEvent] = []
        self._subscribers: set[asyncio.Queue[AgentEvent | None]] = set()
        self._done = False
        self.store = get_store()
        self.paper_fetches = PaperFetchSession()
        self.reuse_cached_claims = reuse_cached_claims

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
        run_started = time()
        try:
            await self.store.put_job(job.model_dump(mode="json"))
            settings = get_settings()
            with token_budget(settings.app_per_paper_token_budget):
                stage_started = time()
                await ensure_indexes()
                self._record_timing(job, "ensure_indexes", stage_started)
                await self._run_inner(job)
                self._record_timing(job, "total", run_started)
                job.updated_at = _now()
                await self.store.put_job(job.model_dump(mode="json"))
                await self._emit("performance", {"timings_ms": job.timings_ms})
                await self._emit("complete", {"protocol_id": job.protocol_id})
        except Exception as e:
            error_message = _error_message(e)
            log.exception("runner.failed", error=error_message)
            job.status = JobStatus.FAILED
            job.error = error_message
            self._record_timing(job, "total", run_started)
            job.updated_at = _now()
            await self.store.put_job(job.model_dump(mode="json"))
            await self._emit("error", {"message": error_message})
        finally:
            self._done = True
            for queue in list(self._subscribers):
                queue.put_nowait(None)

    async def _run_inner(self, job: Job) -> None:
        await self._set_status(job, JobStatus.INGESTING, "Resolving paper identifier")

        stage_started = time()
        paper = await ingest_identifier(self.identifier)
        self._record_timing(job, "ingest", stage_started)
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
        settings = get_settings()
        use_cache = (
            settings.app_reuse_cached_claims
            if self.reuse_cached_claims is None
            else self.reuse_cached_claims
        )
        claims = await _load_cached_claims(paper) if use_cache else []
        cache_hit = bool(claims)
        embeddings: list[list[float]] = []
        if cache_hit:
            job.timings_ms["decompose"] = 0.0
            job.timings_ms["initial_claim_index"] = 0.0
            log.info("claims.cache_hit", paper_id=paper.paper_id, n_claims=len(claims))
        else:
            stage_started = time()
            claims = await extract_claims(paper)
            self._record_timing(job, "decompose", stage_started)

            # Index claims before resolution so the corpus is immediately searchable.
            stage_started = time()
            embeddings = await aembed_texts([c.raw_text for c in claims])
            await delete_claims_for_paper(paper.paper_id)
            await bulk_index_claims(claims, embeddings=embeddings)
            self._record_timing(job, "initial_claim_index", stage_started)

        await self._emit("decompose", {
            "n_claims": len(claims),
            "by_specificity": _count_by_specificity(claims),
            "cache_hit": cache_hit,
            "extraction_mode": _extraction_modes(claims),
        })

        if not cache_hit:
            await self._set_status(job, JobStatus.RESOLVING, f"Resolving {len(claims)} claims")
            semaphore = asyncio.Semaphore(settings.app_max_concurrent_claims)
            stage_started = time()

            async def resolve_one(claim: Claim) -> None:
                if claim.specificity == Specificity.FULLY_DESCRIBED:
                    return
                async with semaphore:
                    claim.resolution_status = ResolutionStatus.RESOLVING
                    result = await resolve_claim(
                        claim,
                        paper,
                        on_event=lambda t, d: self._emit_sync(t, d),
                        fetcher=self.paper_fetches.fetch,
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

            resolve_timeout = max(10, settings.app_agent_timeout_seconds - 60)
            try:
                async with asyncio.timeout(resolve_timeout):
                    await asyncio.gather(*(resolve_one(claim) for claim in claims))
            except TimeoutError:
                log.warning(
                    "runner.resolve_timeout",
                    msg="Citation resolution timed out. Assembling partial protocol.",
                )
                terminal = {
                    ResolutionStatus.RESOLVED,
                    ResolutionStatus.INFERRED,
                    ResolutionStatus.TERMINAL_GAP,
                }
                for claim in claims:
                    if claim.resolution_status not in terminal:
                        claim.resolution_status = ResolutionStatus.TERMINAL_GAP
            self._record_timing(job, "resolve", stage_started)
            stage_started = time()
            await bulk_index_claims(claims, embeddings=embeddings)
            self._record_timing(job, "final_claim_index", stage_started)
        else:
            job.timings_ms["resolve"] = 0.0
            job.timings_ms["final_claim_index"] = 0.0

        await self._set_status(job, JobStatus.ASSEMBLING, "Assembling reconstructed protocol")
        stage_started = time()
        protocol = await assemble(paper, claims, job_id=self.job_id)
        self._record_timing(job, "assemble", stage_started)
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

    @staticmethod
    def _record_timing(job: Job, name: str, started: float) -> None:
        job.timings_ms[name] = round((time() - started) * 1000, 1)

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


def _extraction_modes(claims: list[Claim]) -> str:
    return ",".join(sorted({claim.extraction_mode or "unknown" for claim in claims}))


async def _load_cached_claims(paper: Paper) -> list[Claim]:
    settings = get_settings()
    expected_version = settings.methods_extraction_version
    expected_hash = hashlib.sha256(paper.methods_text().encode()).hexdigest()
    documents = await claims_for_paper(paper.paper_id)
    claims: list[Claim] = []
    for document in documents:
        try:
            claim = Claim.model_validate(document)
        except ValueError:
            return []
        if (
            claim.extraction_version != expected_version
            or claim.source_methods_hash != expected_hash
            or claim.resolution_status
            in {ResolutionStatus.UNRESOLVED, ResolutionStatus.RESOLVING}
        ):
            return []
        claims.append(claim)
    return sorted(claims, key=lambda claim: (claim.raw_sentence_id, claim.claim_id))
