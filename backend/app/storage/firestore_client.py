from __future__ import annotations
"""Job + reconstruction store.

Two implementations behind one interface:
  - GCPFirestoreStore: real google-cloud-firestore (only if GCP_PROJECT_ID set
    and the optional `[gcp]` extra is installed).
  - LocalFileStore: JSON-on-disk under ./.local_storage, the default.

The agent runner doesn't care which one it's using.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)


class JobStore:
    async def put_job(self, job: dict[str, Any]) -> None:
        raise NotImplementedError

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    async def put_reconstruction(self, protocol: dict[str, Any]) -> None:
        raise NotImplementedError

    async def get_reconstruction(self, protocol_id: str) -> dict[str, Any] | None:
        raise NotImplementedError


class LocalFileStore(JobStore):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        (self.root / "jobs").mkdir(parents=True, exist_ok=True)
        (self.root / "reconstructions").mkdir(parents=True, exist_ok=True)
        # Per-entity locks so job writes don't block reconstruction writes.
        self._job_locks: dict[str, asyncio.Lock] = {}
        self._rec_locks: dict[str, asyncio.Lock] = {}
        self._lock_guard = asyncio.Lock()

    def _job_path(self, job_id: str) -> Path:
        return self.root / "jobs" / f"{job_id}.json"

    def _reconstruction_path(self, protocol_id: str) -> Path:
        return self.root / "reconstructions" / f"{protocol_id}.json"

    async def _get_job_lock(self, job_id: str) -> asyncio.Lock:
        async with self._lock_guard:
            if job_id not in self._job_locks:
                self._job_locks[job_id] = asyncio.Lock()
            return self._job_locks[job_id]

    async def _get_rec_lock(self, protocol_id: str) -> asyncio.Lock:
        async with self._lock_guard:
            if protocol_id not in self._rec_locks:
                self._rec_locks[protocol_id] = asyncio.Lock()
            return self._rec_locks[protocol_id]

    async def put_job(self, job: dict[str, Any]) -> None:
        lock = await self._get_job_lock(job["job_id"])
        async with lock:
            path = self._job_path(job["job_id"])
            await asyncio.to_thread(_atomic_json_write, path, job)

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        path = self._job_path(job_id)
        if not path.exists():
            return None
        return await asyncio.to_thread(_json_read, path)

    async def put_reconstruction(self, protocol: dict[str, Any]) -> None:
        lock = await self._get_rec_lock(protocol["protocol_id"])
        async with lock:
            path = self._reconstruction_path(protocol["protocol_id"])
            await asyncio.to_thread(_atomic_json_write, path, protocol)

    async def get_reconstruction(self, protocol_id: str) -> dict[str, Any] | None:
        path = self._reconstruction_path(protocol_id)
        if not path.exists():
            return None
        return await asyncio.to_thread(_json_read, path)


_store: JobStore | None = None


def get_store() -> JobStore:
    global _store
    if _store is not None:
        return _store

    settings = get_settings()
    if settings.gcp_project_id and os.getenv("ENABLE_FIRESTORE") == "1":
        try:
            from google.cloud import firestore  # type: ignore[import-not-found]

            log.info("store.firestore.init")
            _store = GCPFirestoreStore(firestore.Client(project=settings.gcp_project_id))
            return _store
        except Exception as e:
            log.warning("store.firestore.unavailable", error=str(e))

    log.info("store.local_file.init", root=settings.local_storage_root)
    _store = LocalFileStore(settings.local_storage_root)
    return _store


class GCPFirestoreStore(JobStore):
    """Thin wrapper — only imported when actually used."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self.settings = get_settings()

    async def put_job(self, job: dict[str, Any]) -> None:
        col = self.settings.firestore_collection_jobs
        await asyncio.to_thread(self.client.collection(col).document(job["job_id"]).set, job)

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        col = self.settings.firestore_collection_jobs
        doc = await asyncio.to_thread(self.client.collection(col).document(job_id).get)
        return doc.to_dict() if doc.exists else None

    async def put_reconstruction(self, protocol: dict[str, Any]) -> None:
        col = self.settings.firestore_collection_reconstructions
        await asyncio.to_thread(
            self.client.collection(col).document(protocol["protocol_id"]).set, protocol
        )

    async def get_reconstruction(self, protocol_id: str) -> dict[str, Any] | None:
        col = self.settings.firestore_collection_reconstructions
        doc = await asyncio.to_thread(self.client.collection(col).document(protocol_id).get)
        return doc.to_dict() if doc.exists else None


def _atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str))
    temporary.replace(path)


def _json_read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
