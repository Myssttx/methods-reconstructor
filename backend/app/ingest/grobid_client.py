"""GROBID — PDF → TEI XML. Only used when no clean XML is available."""

import httpx

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)


async def process_pdf(pdf_bytes: bytes) -> str | None:
    settings = get_settings()
    url = f"{settings.grobid_url}/api/processFulltextDocument"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, files={"input": ("paper.pdf", pdf_bytes, "application/pdf")})
            if resp.status_code != 200:
                log.warning("grobid.bad_status", status=resp.status_code)
                return None
            return resp.text
    except Exception as e:
        log.warning("grobid.unavailable", error=str(e))
        return None
