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
        self._lock = asyncio.Lock()

    def _job_path(self, job_id: str) -> Path:
        return self.root / "jobs" / f"{job_id}.json"

    def _reconstruction_path(self, protocol_id: str) -> Path:
        return self.root / "reconstructions" / f"{protocol_id}.json"

    async def put_job(self, job: dict[str, Any]) -> None:
        async with self._lock:
            path = self._job_path(job["job_id"])
            path.write_text(json.dumps(job, indent=2, default=str))

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        path = self._job_path(job_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    async def put_reconstruction(self, protocol: dict[str, Any]) -> None:
        async with self._lock:
            path = self._reconstruction_path(protocol["protocol_id"])
            path.write_text(json.dumps(protocol, indent=2, default=str))

    async def get_reconstruction(self, protocol_id: str) -> dict[str, Any] | None:
        path = self._reconstruction_path(protocol_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())


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
