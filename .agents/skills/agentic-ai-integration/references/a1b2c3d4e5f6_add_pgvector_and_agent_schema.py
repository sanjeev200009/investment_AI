"""add_pgvector_and_agent_schema

Revision ID: a1b2c3d4e5f6
Revises: 9c7bb6e6ce19
Create Date: 2026-06-28 00:00:00.000000

Adds:
  - pgvector extension
  - embedding column (vector 1024) on news_sentiment
  - device_token on user_profiles
  - watchlist table
  - user_language on user_profiles
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9c7bb6e6ce19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector — Supabase has this available; run ONCE per project
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add embedding column to news_sentiment (1024-dim NVIDIA NIM embeddings)
    op.execute(
        "ALTER TABLE news_sentiment ADD COLUMN IF NOT EXISTS "
        "embedding vector(1024)"
    )

    # Create an IVFFlat index for fast approximate nearest-neighbour search
    # lists=100 is a good default for up to ~1M rows
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_sentiment_embedding "
        "ON news_sentiment USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )

    # Add device_token for FCM push
    op.add_column(
        "user_profiles",
        sa.Column("device_token", sa.String(512), nullable=True),
    )

    # Add preferred language (en | si | ta)
    op.add_column(
        "user_profiles",
        sa.Column("language", sa.String(5), server_default="en", nullable=False),
    )

    # Watchlist table
    op.create_table(
        "watchlist",
        sa.Column("watchlist_id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),  # type: ignore[attr-defined]
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),
    )
    op.create_index("idx_watchlist_user_id", "watchlist", ["user_id"])


def downgrade() -> None:
    op.drop_table("watchlist")
    op.drop_column("user_profiles", "language")
    op.drop_column("user_profiles", "device_token")
    op.execute("DROP INDEX IF EXISTS idx_news_sentiment_embedding")
    op.execute("ALTER TABLE news_sentiment DROP COLUMN IF EXISTS embedding")
    # Note: we do NOT drop the vector extension as other tables may use it
