"""OpenAI embedding wrapper for text-embedding-3-small."""

from __future__ import annotations

from backend.clients import get_openai_client
from backend.config import get_settings
from backend.utils import retry_openai


@retry_openai()
async def embed_text(text: str) -> list[float]:
    """Generate a 1536-dimensional embedding for the given text."""
    client = get_openai_client()
    settings = get_settings()
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding


@retry_openai()
async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts in a single API call."""
    if not texts:
        return []
    client = get_openai_client()
    settings = get_settings()
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]
