"""market data integrity: snapshot index, latest-quote table, drop redundant index

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-27 00:00:00.000000

Why this is needed
------------------
``market_data`` is append-only and grows at roughly 300 symbols x 4 scrapes/hour.
Every read path derived "the current price" from that history at request time,
each in a different and wrong way -- see the ``MarketDataLatest`` docstring in
app/models/stock.py for the four variants and what each got wrong.

``ix_market_data_symbol_recorded_at``
    The composite index latest-per-symbol lookups and any future per-symbol time
    series need. ``ix_market_data_symbol`` alone cannot serve the ordering, so
    every "latest for this symbol" query sorted a growing per-symbol bucket.

``market_data_latest``
    One row per symbol, upserted by the scrape task in the same transaction as
    the history insert. Backfilled here from existing history so the endpoints
    that now read it are correct immediately rather than empty until the next
    scrape.

``ix_market_data_market_id`` and ``ix_market_data_symbol`` (both dropped)
    The first was a plain btree on the primary key, which ``market_data_pkey``
    already provides as a unique btree. The second is subsumed by the new
    composite index -- ``symbol`` leads it, so it serves every symbol-only
    predicate the standalone index did. Neither served a read the remaining
    indexes cannot, and each cost a write on every insert: at ~6,000 inserts a
    day that is pure overhead. Both are recreated by ``downgrade`` so the
    migration is genuinely reversible.

The backfill picks the newest row per symbol with DISTINCT ON, which is the
Postgres-native form of the query the application code used to run per request.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_market_data_symbol_recorded_at",
        "market_data",
        ["symbol", sa.text("recorded_at DESC")],
    )

    op.create_table(
        "market_data_latest",
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("change", sa.Float(), nullable=True),
        sa.Column("change_pct", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("symbol"),
    )

    # Backfill from existing history. Without this, /stocks/market and the
    # dashboard would return nothing between this migration and the next scrape.
    op.execute("""
        INSERT INTO market_data_latest (
            symbol, market_id, price, change, change_pct, volume, market_cap,
            recorded_at, updated_at)
        SELECT DISTINCT ON (symbol)
            symbol, market_id, price, change, change_pct, volume, market_cap,
            recorded_at, now()
        FROM market_data
        ORDER BY symbol, recorded_at DESC, market_id DESC
    """)

    op.drop_index("ix_market_data_market_id", table_name="market_data")
    op.drop_index("ix_market_data_symbol", table_name="market_data")


def downgrade() -> None:
    op.create_index("ix_market_data_symbol", "market_data", ["symbol"])
    op.create_index("ix_market_data_market_id", "market_data", ["market_id"])
    op.drop_table("market_data_latest")
    op.drop_index("ix_market_data_symbol_recorded_at", table_name="market_data")
