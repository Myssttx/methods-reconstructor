from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import require_api_key
from app.ingest.fixtures import list_fixture_ids
from app.ingest.pipeline import ingest_identifier
from app.logging import get_logger
from app.search.papers_dao import get_paper

log = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_api_key)])


class IngestRequest(BaseModel):
    identifier: str


@router.post("/ingest")
async def ingest(req: IngestRequest):
    paper = await ingest_identifier(req.identifier)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"Could not resolve {req.identifier}")
    return {
        "paper_id": paper.paper_id,
        "title": paper.title,
        "status": "ingested",
        "has_methods": bool(paper.methods_text()),
    }


@router.get("/{paper_id}")
async def get_paper_by_id(paper_id: str):
    doc = await get_paper(paper_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return doc


@router.get("/_/fixtures")
async def list_fixtures():
    return {"fixtures": list_fixture_ids()}
