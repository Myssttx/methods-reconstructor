"""Sentence embeddings.

Uses sentence-transformers (all-MiniLM-L6-v2, 384-dim) locally so the stack
works without cloud creds. Set GOOGLE_API_KEY + ENABLE_VERTEX_EMBEDDINGS=1 to
swap in Vertex AI text-embedding-005 (768-dim — also bump the index mappings).
"""

import os
import threading
from asyncio import to_thread

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
    return await to_thread(embed_texts, texts)


async def aembed_text(text: str) -> list[float]:
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
