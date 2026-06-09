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
    location = settings.vertex_ai_location or settings.gcp_region
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
        for start in range(0, len(texts), 5):
            batch = texts[start : start + 5]
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


@lru_cache
def _vertex_auth(credentials_path: str, project_id: str) -> GoogleAccessTokenProvider:
    return GoogleAccessTokenProvider(
        credentials_path=credentials_path,
        project_id=project_id,
    )
