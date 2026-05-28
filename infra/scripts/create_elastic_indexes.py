"""Idempotent: create the papers + claims indexes in the configured Elastic.

Run as:  docker-compose exec backend python -m infra.scripts.create_elastic_indexes
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.logging import configure_logging  # noqa: E402
from app.search.indexes import ensure_indexes  # noqa: E402


async def main() -> None:
    configure_logging()
    await ensure_indexes()
    print("OK: papers + claims indexes ready.")


if __name__ == "__main__":
    asyncio.run(main())
