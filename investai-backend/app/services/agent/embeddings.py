# app/services/agent/embeddings.py
"""
NVIDIA NIM embedding service.
Generates 1024-dimensional embeddings for RAG via pgvector.
Model: nvidia/nv-embedqa-e5-v5 (best for financial Q&A retrieval)
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import List

import httpx

logger = logging.getLogger(__name__)

NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
EMBED_DIM = 1024
BATCH_SIZE = 32  # NVIDIA NIM max batch size


def _get_nvidia_key() -> str:
    from app.config import get_settings
    s = get_settings()
    key = getattr(s, "NVIDIA_API_KEY", "")
    if not key:
        raise RuntimeError(
            "NVIDIA_API_KEY not set in .env — needed for embeddings"
        )
    return key


async def get_embedding(text: str) -> list[float]:
    """Embed a single string. Returns a list of floats (length=EMBED_DIM)."""
    results = await get_embeddings_batch([text])
    return results[0]


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of strings. Splits into sub-batches of BATCH_SIZE
    and makes parallel requests.
    """
    if not texts:
        return []

    api_key = _get_nvidia_key()
    all_embeddings: list[list[float]] = []

    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            response = await client.post(
                NVIDIA_EMBED_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": NVIDIA_EMBED_MODEL,
                    "input": batch,
                    "input_type": "query",
                    "encoding_format": "float",
                    "truncate": "END",
                },
            )
            response.raise_for_status()
            data = response.json()
            # data["data"] is sorted by index
            sorted_items = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend(item["embedding"] for item in sorted_items)

    return all_embeddings


async def embed_and_store_news(news_ids: list[int], db) -> int:
    """
    Background helper: fetch unembedded news rows, embed them in batch,
    write embeddings back. Returns count of rows updated.
    Called by the Celery sentiment task after scraping.
    """
    from app.models.stock import NewsSentiment
    from sqlalchemy import text as sql_text

    rows = (
        db.query(NewsSentiment)
        .filter(
            NewsSentiment.news_id.in_(news_ids),
        )
        .all()
    )
    if not rows:
        return 0

    texts = [f"{r.headline}. {r.summary or ''}" for r in rows]
    try:
        embeddings = await get_embeddings_batch(texts)
    except Exception as e:
        logger.error("Embedding batch failed: %s", e)
        return 0

    count = 0
    for row, emb in zip(rows, embeddings):
        db.execute(
            sql_text(
                "UPDATE news_sentiment SET embedding = cast(:vec AS vector) "
                "WHERE news_id = :nid"
            ),
            {"vec": str(emb), "nid": row.news_id},
        )
        count += 1

    db.commit()
    logger.info("Embedded %d news rows", count)
    return count
