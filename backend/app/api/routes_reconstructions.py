import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.agent.runner import JobCapacityError, get_runner, start_job
from app.logging import get_logger
from app.storage.firestore_client import get_store

log = get_logger(__name__)
router = APIRouter()


class ReconstructionRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=2048)


@router.post("")
async def create_reconstruction(req: ReconstructionRequest):
    try:
        runner = start_job(req.identifier.strip())
    except JobCapacityError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    return {
        "job_id": runner.job_id,
        "stream_url": f"/api/reconstructions/{runner.job_id}/stream",
    }


@router.get("/{job_id}")
async def get_job(job_id: str):
    store = get_store()
    job = await store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/stream")
async def stream(job_id: str, request: Request):
    runner = get_runner(job_id)
    store = get_store()
    job = await store.get_job(job_id)
    if runner is None and job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        if runner is not None:
            async for ev in runner.stream():
                if await request.is_disconnected():
                    break
                yield {"data": json.dumps(ev.model_dump())}
            return

        status = job.get("status")
        timestamp = job.get("updated_at", "")
        yield {
            "data": json.dumps(
                {
                    "type": "status",
                    "timestamp": timestamp,
                    "data": {"status": status, "message": "Loaded persisted job state"},
                }
            )
        }
        event_type = "complete" if status == "complete" else "error"
        event_data = (
            {"protocol_id": job.get("protocol_id")}
            if status == "complete"
            else {
                "message": job.get("error")
                or "The worker stopped before this job completed"
            }
        )
        yield {
            "data": json.dumps(
                {
                    "type": event_type,
                    "timestamp": timestamp,
                    "data": event_data,
                }
            )
        }

    return EventSourceResponse(event_generator())


@router.get("/{job_id}/protocol")
async def get_protocol(job_id: str):
    store = get_store()
    job = await store.get_job(job_id)
    if not job or not job.get("protocol_id"):
        raise HTTPException(status_code=404, detail="No protocol yet for this job")
    proto = await store.get_reconstruction(job["protocol_id"])
    if proto is None:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return proto
