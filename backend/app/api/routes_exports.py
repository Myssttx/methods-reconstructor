import asyncio
import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import require_api_key
from app.exporting.pdf_export import collect_source_usage, render_protocol_pdf
from app.logging import get_logger
from app.search.papers_dao import get_paper
from app.storage.firestore_client import get_store

log = get_logger(__name__)
router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/{job_id}/export.{fmt}")
async def export(job_id: str, fmt: str):
    store = get_store()
    job = await store.get_job(job_id)
    if not job or not job.get("protocol_id"):
        raise HTTPException(status_code=404, detail="No protocol yet for this job")
    proto = await store.get_reconstruction(job["protocol_id"])
    if proto is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    if fmt == "json":
        return Response(
            content=json.dumps(proto, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="protocol-{job_id}.json"'},
        )

    if fmt == "md":
        return Response(
            content=_to_markdown(proto),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="protocol-{job_id}.md"'},
        )

    if fmt == "csv":
        return Response(
            content=_gaps_to_csv(proto),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="gaps-{job_id}.csv"'},
        )

    if fmt == "pdf":
        source_ids = list(collect_source_usage(proto))
        source_documents = await asyncio.gather(*(get_paper(source_id) for source_id in source_ids))
        source_metadata = {
            source_id: document or {}
            for source_id, document in zip(source_ids, source_documents, strict=True)
        }
        return Response(
            content=render_protocol_pdf(proto, source_metadata),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="protocol-{job_id}.pdf"'},
        )

    raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")


def _to_markdown(proto: dict) -> str:
    lines = [
        f"# Reconstructed Protocol: {proto.get('title', '')}",
        "",
        f"**Source paper:** `{proto.get('source_paper_id')}`",
        f"**Methods evidence coverage:** "
        f"{proto.get('methods_evidence_score', proto.get('reproducibility_score', 0))} / 100",
        "",
        str(proto.get("score_methodology", "")),
        "",
        "## Section scores",
        "",
    ]
    for s in proto.get("section_scores", []):
        lines.append(f"- **{s['section']}**: {s['score']:.0f} ({s['n_resolved']}/{s['n_claims']} resolved)")
    lines.append("")

    for section_name, claims in (proto.get("sections") or {}).items():
        lines.append(f"## {section_name.replace('_', ' ').title()}")
        lines.append("")
        for c in claims:
            text = c.get("resolved_text") or c.get("raw_text", "")
            lines.append(f"- {text}")
            if c.get("resolution_status") == "inferred":
                lines.append("  - *Corpus inference; not evidence-backed.*")
            chain = c.get("resolution_chain") or []
            if chain:
                src = chain[-1].get("source_paper_id", "?")
                lines.append(f"  - *Source: {src}*")
        lines.append("")

    if proto.get("gaps"):
        lines.append("## Gap Report")
        lines.append("")
        for g in proto["gaps"]:
            lines.append(f"- **{g.get('reason', 'unknown')}**: {g.get('raw_text', '')}")
            if g.get("suggested_action"):
                lines.append(f"  - Next step: {g['suggested_action']}")
        lines.append("")
    return "\n".join(lines)


def _gaps_to_csv(proto: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["claim_id", "reason", "raw_text", "suggested_action"])
    for g in proto.get("gaps", []):
        writer.writerow(
            [g.get("claim_id", ""), g.get("reason", ""), g.get("raw_text", ""), g.get("suggested_action", "")]
        )
    return buf.getvalue()
