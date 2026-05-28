"""Load every paper in tests/fixtures/papers/*.json into the configured Elastic.

Useful so the recursive resolver has cited papers to actually resolve into.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.ingest.fixtures import load_all_fixtures  # noqa: E402
from app.ingest.pipeline import _index_with_sentences  # noqa: E402
from app.logging import configure_logging  # noqa: E402
from app.search.indexes import ensure_indexes  # noqa: E402


async def main() -> None:
    configure_logging()
    await ensure_indexes()
    papers = load_all_fixtures()
    for p in papers:
        await _index_with_sentences(p)
        print(f"indexed: {p.paper_id} — {p.title[:80]}")
    print(f"\nDone. Indexed {len(papers)} fixture paper(s).")


if __name__ == "__main__":
    asyncio.run(main())
