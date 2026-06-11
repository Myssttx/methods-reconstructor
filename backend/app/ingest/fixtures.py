"""Pre-cached demo papers.

Stored as JSON files under backend/tests/fixtures/papers/. Lets the demo
work fully offline and gives the recursive resolver a populated mini-corpus
to actually resolve against.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
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
    """If the identifier matches a bundled fixture paper, return it.

    Matches on (case-insensitive):
      - exact paper_id
      - paper_id with prefix stripped (doi:, arxiv:, fixture:)
      - file stem
      - the fixture's `aliases` list
      - the fixture's title (substring match)
      - first author last name + year combination
    """
    if not FIXTURE_DIR.exists():
        return None
    ident = identifier.strip().lower()
    if not ident:
        return None
    for p in FIXTURE_DIR.glob("*.json"):
        data = json.loads(p.read_text())
        pid = data["paper_id"].lower()
        if ident in (pid, pid.replace("doi:", ""), pid.replace("arxiv:", ""), pid.replace("fixture:", "")):
            return _hydrate(data)
        if ident == p.stem.lower():
            return _hydrate(data)
        aliases = [a.lower() for a in data.get("aliases", [])]
        if ident in aliases:
            return _hydrate(data)
        title = (data.get("title") or "").lower()
        if title and (title in ident or _share_distinctive_token(ident, title)):
            return _hydrate(data)
        if _author_year_match(ident, data):
            return _hydrate(data)
    return None


def _share_distinctive_token(a: str, b: str) -> bool:
    """Cheap title-overlap heuristic — share at least one >5-char token."""
    a_tokens = {t for t in a.replace(",", " ").split() if len(t) > 5}
    b_tokens = {t for t in b.replace(",", " ").split() if len(t) > 5}
    return len(a_tokens & b_tokens) >= 2


def _author_year_match(ident: str, data: dict) -> bool:
    """Match e.g. 'bremer et al., 2021' against a fixture by last name + year."""
    authors = data.get("authors") or []
    year = data.get("year")
    if not authors or not year:
        return False
    first_name = (authors[0].get("name") or "").lower()
    last_name = first_name.split(",")[0].strip().split()[-1] if first_name else ""
    if not last_name:
        return False
    return last_name in ident and str(year) in ident


def load_all_fixtures() -> list[Paper]:
    if not FIXTURE_DIR.exists():
        return []
    return [_hydrate(json.loads(p.read_text())) for p in FIXTURE_DIR.glob("*.json")]


def _hydrate(data: dict) -> Paper:
    if not data.get("ingested_at"):
        data["ingested_at"] = datetime.now(UTC).isoformat()
    return Paper.model_validate(data)
