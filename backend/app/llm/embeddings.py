"""Sentence embeddings.

Uses sentence-transformers (all-MiniLM-L6-v2, 384-dim) locally so the stack
works without cloud credentials. Set ENABLE_VERTEX_EMBEDDINGS=1 to use Vertex
AI text-embedding-005 with 384-dimensional output matching the Elastic mapping.
"""

import os
import threading
from asyncio import to_thread
from functools import lru_cache

import httpx

from app.config import get_settings
from app.llm.google_auth import GoogleAccessTokenProvider
from app.logging import get_logger

log = get_logger(__name__)

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_DIM = 384
_VERTEX_MAX_BATCH_ITEMS = 250
_VERTEX_MAX_BATCH_CHARS = 60_000

_model_lock = threading.Lock()
_model = None


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from sentence_transformers import SentenceTransformer

        log.info("embeddings.load", model=_MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
        return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one vector per input string. Empty input → empty list."""
    if not texts:
        return []

    if os.getenv("EMBEDDINGS_FAKE") == "1":
        return [_hash_vec(t) for t in texts]

    model = _load_model()
    vecs = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vecs]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


async def aembed_texts(texts: list[str]) -> list[list[float]]:
    """Run CPU-bound local embedding work outside the FastAPI event loop."""
    settings = get_settings()
    if settings.enable_vertex_embeddings and settings.resolved_gcp_project_id:
        return await _vertex_embed(texts, task_type="RETRIEVAL_DOCUMENT")
    return await to_thread(embed_texts, texts)


async def aembed_text(text: str) -> list[float]:
    settings = get_settings()
    if settings.enable_vertex_embeddings and settings.resolved_gcp_project_id:
        return (await _vertex_embed([text], task_type="RETRIEVAL_QUERY"))[0]
    return (await aembed_texts([text]))[0]


def embedding_dim() -> int:
    return _DIM


def _hash_vec(text: str) -> list[float]:
    """Deterministic pseudo-embedding for unit tests (no model download)."""
    import hashlib
    import math

    h = hashlib.sha256(text.encode()).digest()
    # repeat hash to fill DIM floats in [-1, 1], then L2-normalize
    raw = []
    for i in range(_DIM):
        b = h[i % len(h)]
        raw.append((b - 128) / 128.0)
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]


async def _vertex_embed(texts: list[str], *, task_type: str) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    project_id = settings.resolved_gcp_project_id
    location = _vertex_embedding_location(
        settings.vertex_ai_location,
        settings.gcp_region,
    )
    auth = _vertex_auth(settings.adc_credentials_path, project_id)
    token = await auth.token()
    url = (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/publishers/google/models/"
        f"{settings.gemini_embedding_model}:predict"
    )
    timeout = httpx.Timeout(
        settings.llm_request_timeout_seconds,
        connect=30.0,
        write=30.0,
        pool=30.0,
    )
    vectors: list[list[float]] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for batch in _embedding_batches(texts):
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "x-goog-user-project": auth.quota_project_id,
                },
                json={
                    "instances": [
                        {"content": text, "task_type": task_type}
                        for text in batch
                    ],
                    "parameters": {"outputDimensionality": _DIM},
                },
            )
            response.raise_for_status()
            predictions = response.json().get("predictions") or []
            vectors.extend(
                prediction.get("embeddings", {}).get("values") or []
                for prediction in predictions
            )
    if len(vectors) != len(texts) or any(len(vector) != _DIM for vector in vectors):
        raise RuntimeError("Vertex embedding response had an unexpected shape")
    return vectors


def _embedding_batches(texts: list[str]) -> list[list[str]]:
    """Pack requests below Vertex's item and aggregate token limits."""
    batches: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for text in texts:
        text_chars = len(text)
        if current and (
            len(current) >= _VERTEX_MAX_BATCH_ITEMS
            or current_chars + text_chars > _VERTEX_MAX_BATCH_CHARS
        ):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(text)
        current_chars += text_chars
    if current:
        batches.append(current)
    return batches


def _vertex_embedding_location(vertex_location: str, gcp_region: str) -> str:
    """Embedding models use a regional endpoint even when Gemini uses global."""
    if vertex_location and vertex_location != "global":
        return vertex_location
    return gcp_region or "us-central1"


@lru_cache
def _vertex_auth(credentials_path: str, project_id: str) -> GoogleAccessTokenProvider:
    return GoogleAccessTokenProvider(
        credentials_path=credentials_path,
        project_id=project_id,
    )
