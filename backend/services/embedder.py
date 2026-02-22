"""OpenAI embedding wrapper for text-embedding-3-small with in-process LRU cache."""

from __future__ import annotations

import hashlib
from collections import OrderedDict

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import retry_openai

# ---------------------------------------------------------------------------
# In-process LRU cache — survives for the lifetime of the process.
# Embeddings are fully deterministic (same text → same vector), so there is
# no correctness risk in caching indefinitely. 2 000 entries ≈ 3–4 MB RAM.
# ---------------------------------------------------------------------------
_CACHE_MAX = 2_000
_cache: OrderedDict[str, list[float]] = OrderedDict()


def _cache_get(text: str) -> list[float] | None:
    key = hashlib.sha256(text.encode()).hexdigest()
    if key not in _cache:
        return None
    # Move to end (most-recently-used)
    _cache.move_to_end(key)
    return _cache[key]


def _cache_set(text: str, embedding: list[float]) -> None:
    key = hashlib.sha256(text.encode()).hexdigest()
    if len(_cache) >= _CACHE_MAX:
        _cache.popitem(last=False)  # evict least-recently-used
    _cache[key] = embedding


# ---------------------------------------------------------------------------
# Internal OpenAI caller — retry decorator lives here, not on the public API
# ---------------------------------------------------------------------------

@retry_openai()
async def _call_openai_embeddings(texts: list[str]) -> list[list[float]]:
    client = get_openai_client()
    settings = get_settings()
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def embed_text(text: str) -> list[float]:
    """Generate a 1536-dimensional embedding, served from cache when possible."""
    cached = _cache_get(text)
    if cached is not None:
        return cached
    result = (await _call_openai_embeddings([text]))[0]
    _cache_set(text, result)
    return result


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts, only calling the API for cache misses."""
    if not texts:
        return []

    results: list[list[float] | None] = [_cache_get(t) for t in texts]

    miss_indices = [i for i, r in enumerate(results) if r is None]
    if miss_indices:
        miss_texts = [texts[i] for i in miss_indices]
        embeddings = await _call_openai_embeddings(miss_texts)
        for idx, emb in zip(miss_indices, embeddings):
            _cache_set(texts[idx], emb)
            results[idx] = emb

    return results  # type: ignore[return-value]
