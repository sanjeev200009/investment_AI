# app/services/agent/embeddings.py
"""
NVIDIA NIM embedding service for RAG over pgvector.

Model: nvidia/nemotron-3-embed-1b, 2048 dimensions.

The previous model (nvidia/nv-embedqa-e5-v5, 1024-dim) reached end of life and
now returns HTTP 410 Gone, so every embedding call was failing silently — the
Celery task logged an error and returned 0, leaving search_financial_knowledge
permanently on its keyword fallback.

This model is *asymmetric*: stored documents must be embedded with
input_type="passage" and search queries with input_type="query". Measured on the
live endpoint, the two produce materially different vectors for identical text
(cosine 0.60 vs 0.43), so mixing them degrades retrieval. The old code embedded
everything as "query", including stored documents.
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
BATCH_SIZE = 32  # NVIDIA NIM max batch size, verified against the live endpoint

# Characters of article body folded into a stored news vector. Bounded so a long
# feature cannot crowd out the other 31 documents in its batch; news writing puts
# the substance in the first few paragraphs, and the two live sources' stories
# measured 1,339 and 2,583 characters in total.
EMBED_BODY_CHARS = 1200

InputType = Literal["query", "passage"]


def _embed_config() -> tuple[str, str, int]:
    """(api_key, model, dim) — read at call time so .env changes need no restart
    of anything but the process, and so import never fails on a missing key."""
    from app.config import get_settings
    s = get_settings()
    key = getattr(s, "NVIDIA_API_KEY", "")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY not set in .env — needed for embeddings")
    return key, s.NVIDIA_EMBED_MODEL, s.EMBED_DIM


async def get_embedding(text: str, input_type: InputType = "query") -> list[float]:
    """Embed a single string. Defaults to "query" because the only single-string
    caller is the RAG search in tools.py."""
    results = await get_embeddings_batch([text], input_type=input_type)
    return results[0]


async def get_embeddings_batch(
    texts: list[str], input_type: InputType = "passage"
) -> list[list[float]]:
    """
    Embed a batch of strings in sub-batches of BATCH_SIZE.

    Defaults to "passage" because batch embedding is how documents get indexed.
    """
    if not texts:
        return []

    api_key, model, dim = _embed_config()
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
                    "model": model,
                    "input": batch,
                    "input_type": input_type,
                    "encoding_format": "float",
                    "truncate": "END",
                },
            )
            response.raise_for_status()
            data = response.json()
            # data["data"] is not guaranteed ordered; sort by index before zipping
            # against the input texts.
            sorted_items = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend(item["embedding"] for item in sorted_items)

    # A dimension mismatch means the column and the model have diverged — better
    # to fail loudly here than to have Postgres reject every UPDATE downstream.
    if all_embeddings and len(all_embeddings[0]) != dim:
        raise RuntimeError(
            f"{model} returned {len(all_embeddings[0])}-dim vectors but EMBED_DIM "
            f"is {dim}; the news_sentiment.embedding column must match"
        )
    return all_embeddings


async def embed_and_store_news(news_ids: list[int], db) -> int:
    """
    Background helper: fetch news rows, embed them in batch, write embeddings
    back. Returns count of rows updated.
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

    # Headline, then the summary, then the article's own opening. Before I-08 this
    # was `f"{r.headline}. {r.summary or ''}"` and `summary` was the literal string
    # "Editorial :" on every row — so the vector encoded a headline plus an
    # identical suffix on all 60 documents, and `search_financial_knowledge` was
    # retrieving on headline similarity alone with a constant added to every point.
    #
    # The body is included because retrieval quality is the whole reason this
    # column exists: a question about a rights issue matches the paragraph that
    # explains it, not the headline that does not mention it. Capped at
    # EMBED_BODY_CHARS so a long feature does not dominate the batch's token
    # budget; the lede carries the substance in news writing.
    texts = [
        ". ".join(part for part in (
            r.headline,
            (r.summary or "").strip(),
            (r.body or "")[:EMBED_BODY_CHARS].strip(),
        ) if part)
        for r in rows
    ]
    try:
        # Stored documents, not queries — see the module docstring.
        embeddings = await get_embeddings_batch(texts, input_type="passage")
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
