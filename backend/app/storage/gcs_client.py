"""Blob store: GCS in cloud, local filesystem otherwise."""

import asyncio
from pathlib import Path

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)


class BlobStore:
    async def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError

    async def get(self, key: str) -> bytes | None:
        raise NotImplementedError


class LocalBlobStore(BlobStore):
    def __init__(self, root: str) -> None:
        self.root = Path(root) / "blobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        async with self._lock:
            path.write_bytes(data)
        return str(path)

    async def get(self, key: str) -> bytes | None:
        path = self.root / key
        if not path.exists():
            return None
        return path.read_bytes()


_blobs: BlobStore | None = None


def get_blobs() -> BlobStore:
    global _blobs
    if _blobs is None:
        settings = get_settings()
        log.info("blobs.local_file.init", root=settings.local_storage_root)
        _blobs = LocalBlobStore(settings.local_storage_root)
    return _blobs
