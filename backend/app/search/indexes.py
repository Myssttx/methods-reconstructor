"""Index bootstrap helpers — read mappings from infra/elastic/*.json."""

import json
from pathlib import Path

from app.config import get_settings
from app.logging import get_logger
from app.search.elastic_client import get_es

log = get_logger(__name__)

MAPPINGS_ROOT = Path(__file__).resolve().parents[3] / "infra" / "elastic"


def _load_mapping(name: str) -> dict:
    return json.loads((MAPPINGS_ROOT / f"{name}_index.json").read_text())


async def ensure_indexes() -> None:
    """Create papers + claims indexes if they don't already exist."""
    settings = get_settings()
    es = get_es()

    for index_name, file_stem in [
        (settings.elastic_papers_index, "papers"),
        (settings.elastic_claims_index, "claims"),
    ]:
        exists = await es.indices.exists(index=index_name)
        if exists:
            log.info("elastic.index.exists", index=index_name)
            continue
        mapping = _load_mapping(file_stem)
        await es.indices.create(index=index_name, **mapping)
        log.info("elastic.index.created", index=index_name)
