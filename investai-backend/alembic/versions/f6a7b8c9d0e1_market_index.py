"""market_index and market_index_latest (I-05: real index values)

The dashboard returned ASPI as a literal 12450.80 / +1.2%, with a code comment
admitting it. The real value at the time of writing was 21279.65 / -0.31% -- out
by 71% and wrong in sign. cse.lk's ``allSectors`` endpoint carries all 22
indices (ASPI, S&P SL20, and 20 GICS industry groups) in a single call, and its
values agree exactly with the dedicated ``aspiData``/``snpData`` endpoints and
with ``dailyMarketSummery``.

Nothing to backfill: no index data has ever been stored. Readers must therefore
tolerate an empty table, which is why the dashboard returns ``aspi: null`` rather
than a placeholder number when no reading exists.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # History. recorded_at is the exchange's own transactionTime, not our scrape
    # clock, because cse.lk keeps serving the last session's close while the
    # market is shut.
    op.create_table(
        "market_index",
        sa.Column("index_id", sa.Integer(), primary_key=True),
        sa.Column("index_code", sa.String(length=20), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("change", sa.Float(), nullable=True),
        sa.Column("change_pct", sa.Float(), nullable=True),
        sa.Column("previous_close", sa.Float(), nullable=True),
        # NULL for ASPI and S&P SL20; cse.lk reports activity per industry group.
        sa.Column("turnover", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("trades", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        # Makes a re-scrape of an unchanged reading a no-op instead of a
        # duplicate row -- the task runs every 15 minutes and the index only
        # moves during a session. The same btree is scanned backwards for
        # `WHERE index_code = ? ORDER BY recorded_at DESC`, so no second index
        # is needed here (unlike market_data, which has no such constraint).
        sa.UniqueConstraint("index_code", "recorded_at",
                            name="uq_market_index_code_recorded_at"),
    )

    op.create_table(
        "market_index_latest",
        sa.Column("index_code", sa.String(length=20), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("change", sa.Float(), nullable=True),
        sa.Column("change_pct", sa.Float(), nullable=True),
        sa.Column("previous_close", sa.Float(), nullable=True),
        sa.Column("turnover", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("trades", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("market_index_latest")
    op.drop_table("market_index")
