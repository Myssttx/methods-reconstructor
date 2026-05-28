"""Pre-cached demo papers.

Stored as JSON files under backend/tests/fixtures/papers/. Lets the demo
work fully offline and gives the recursive resolver a populated mini-corpus
to actually resolve against.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.logging import get_logger
from app.models import Paper

log = get_logger(__name__)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "papers"


def list_fixture_ids() -> list[str]:
    if not FIXTURE_DIR.exists():
        return []
    out = []
    for p in FIXTURE_DIR.glob("*.json"):
        data = json.loads(p.read_text())
        out.append(data["paper_id"])
    return out


def try_load_fixture(identifier: str) -> Paper | None:
    """If the identifier matches a bundled fixture paper, return it."""
    if not FIXTURE_DIR.exists():
        return None
    ident = identifier.strip().lower()
    for p in FIXTURE_DIR.glob("*.json"):
        data = json.loads(p.read_text())
        pid = data["paper_id"].lower()
        if ident in (pid, pid.replace("doi:", ""), pid.replace("arxiv:", "")):
            return _hydrate(data)
        # also match by file stem
        if ident == p.stem.lower():
            return _hydrate(data)
    return None


def load_all_fixtures() -> list[Paper]:
    if not FIXTURE_DIR.exists():
        return []
    return [_hydrate(json.loads(p.read_text())) for p in FIXTURE_DIR.glob("*.json")]


def _hydrate(data: dict) -> Paper:
    if not data.get("ingested_at"):
        data["ingested_at"] = datetime.now(timezone.utc).isoformat()
    return Paper.model_validate(data)
