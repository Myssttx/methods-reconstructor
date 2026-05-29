import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent.runner import get_runner, start_job
from app.logging import get_logger
from app.storage.firestore_client import get_store

log = get_logger(__name__)
router = APIRouter()


class ReconstructionRequest(BaseModel):
    identifier: str


@router.post("")
async def create_reconstruction(req: ReconstructionRequest):
    runner = start_job(req.identifier)
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
    if runner is None:
        raise HTTPException(status_code=404, detail="No active stream for this job")

    async def event_generator():
        async for ev in runner.stream():
            if await request.is_disconnected():
                break
            yield {"data": json.dumps(ev.model_dump())}

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
