"""widen news_sentiment.embedding to 2048 dims for nemotron-3-embed-1b

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-26 00:00:00.000000

Why this is needed
------------------
The embedding model this project was built against, nvidia/nv-embedqa-e5-v5
(1024-dim), reached end of life and the endpoint now returns HTTP 410 Gone. Every
embedding call was failing, so news_sentiment.embedding was never populated and
the agent's search_financial_knowledge tool ran permanently on its keyword
fallback instead of on RAG.

The available replacement on NVIDIA NIM, nvidia/nemotron-3-embed-1b, emits 2048
dimensions and rejects a `dimensions` override ("dimensions must be one of
2048"), so the column has to widen to match.

Why the ANN index is dropped rather than rebuilt
------------------------------------------------
pgvector's ivfflat and hnsw index types both cap at 2000 dimensions, so a
vector(2048) column cannot carry either. Removing the index means cosine search
becomes an exact sequential scan.

That is the right trade here: this corpus is scraped CSE news in the
hundreds-to-low-thousands of rows, where a sequential scan is a few milliseconds
and returns *exact* nearest neighbours — ivfflat is approximate and would trade
recall for speed we do not need at this scale. If the corpus ever grows past
~100k rows, the options are to reduce dimensionality (e.g. store a 1024-dim
projection alongside) or move to an index type that supports high dimensions.

Existing embeddings
-------------------
Any vectors already stored are 1024-dim and cannot be widened in place, so the
column is dropped and recreated. Nothing is lost that is not regenerable: the
Celery task tasks.scrape_tasks.embed_news_articles re-embeds from headline and
summary, which stay in the table.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ivfflat/hnsw cannot index >2000 dims; drop before altering the column.
    op.execute("DROP INDEX IF EXISTS idx_news_sentiment_embedding")

    # Stored 1024-dim vectors are not convertible to 2048, and are cheap to
    # regenerate, so drop and recreate rather than attempt a cast.
    op.execute("ALTER TABLE news_sentiment DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE news_sentiment ADD COLUMN embedding vector(2048)")

    # Exact search still benefits from skipping unembedded rows, which is what
    # the query's `WHERE embedding IS NOT NULL` filters on.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_sentiment_embedding_present "
        "ON news_sentiment (news_id) WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_news_sentiment_embedding_present")
    op.execute("ALTER TABLE news_sentiment DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE news_sentiment ADD COLUMN embedding vector(1024)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_sentiment_embedding "
        "ON news_sentiment USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
