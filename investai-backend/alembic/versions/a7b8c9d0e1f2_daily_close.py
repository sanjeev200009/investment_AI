"""daily_close, portfolio_snapshots, market_data.last_traded_at (I-06: real history)

Two charts were drawn from invented numbers. ``StockDetailScreen.js`` built its
price series with ``Math.random()`` and labelled the points with real clock times.
``dashboard.py`` served ``weekly_history`` as ``current_value x [0.85, 0.82,
0.94, 1.0]`` -- four points derived from the present value, so the line could only
ever show a dip recovering to exactly today, whatever the portfolio had done.

This adds the two tables those charts need, and the column without which the
price one cannot be honest.

**``market_data.last_traded_at``.** The trade summary carries a per-symbol
``lastTradedTime`` and the scraper was discarding it. Without it there is no way
to know which *session* a quote belongs to: cse.lk keeps serving the last
session's numbers while the market is shut, so a Thursday scrape of Tuesday's
close is stamped Thursday. The two snapshots in ``market_data`` when this was
written demonstrate both failure modes -- one stamped 2026-07-05, a **Sunday**,
when the CSE does not trade, and one stamped 2026-08-27 carrying the 2026-08-25
session.

Nullable, and **not backfilled**: those rows never captured the exchange's
timestamp, and cse.lk publishes no history endpoint to recover it from
(``chartData`` returns 400 for every parameter combination tried). Guessing would
mean inventing a date, which is the thing this migration exists to stop.

**Nothing to backfill into ``daily_close`` either**, for the same reason. Its
``trade_date`` comes from ``last_traded_at``, so the pre-existing history cannot
supply one -- and those rows carry no open/high/low regardless. The series starts
from the first scrape after this migration. A chart with three real points and a
stated point count is defensible; one padded to twenty with guessed dates is not.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""
from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── The exchange's own timestamp, on both quote tables ────────────────────
    #
    # Additive and nullable, so this half of the migration cannot fail on
    # existing data and needs no table rewrite.
    op.add_column("market_data",
                  sa.Column("last_traded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("market_data_latest",
                  sa.Column("last_traded_at", sa.DateTime(timezone=True), nullable=True))

    # ── daily_close ──────────────────────────────────────────────────────────
    #
    # (symbol, trade_date) as the primary key gives idempotence and the read index
    # in one object. Ascending rather than DESC, unlike ix_market_data_symbol_-
    # recorded_at: a chart reads a contiguous forward span oldest-first, it does
    # not seek the single newest row.
    op.create_table(
        "daily_close",
        sa.Column("symbol", sa.String(length=20), primary_key=True),
        sa.Column("trade_date", sa.Date(), primary_key=True),
        # open/high/low are nullable because they are the exchange's, and a symbol
        # that has only printed one trade legitimately has no range yet. close is
        # NOT NULL -- a row with no close is not a data point.
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("previous_close", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("turnover", sa.Float(), nullable=True),
        sa.Column("trades", sa.Integer(), nullable=True),
        # Source of trade_date and the ordering key for the upsert's
        # no-backwards guard, so NOT NULL: a row that cannot be compared cannot
        # be safely updated.
        sa.Column("last_traded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )

    # ── portfolio_snapshots ──────────────────────────────────────────────────
    #
    # ON DELETE CASCADE here where market_data_latest.market_id deliberately has
    # no foreign key. The distinction is what the row means: a stale copy of a
    # quote is still a true statement about the past and must survive its source
    # being pruned, whereas a valuation of a portfolio that no longer exists is
    # not a fact about anything.
    op.create_table(
        "portfolio_snapshots",
        sa.Column("portfolio_id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False, primary_key=True),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("total_cost", sa.Float(), nullable=False),
        sa.Column("holdings_count", sa.Integer(), nullable=False),
        # Below holdings_count when some holding had no quote and was valued at
        # its cost basis, so a reader can tell a precise valuation from a partial
        # one instead of having to assume.
        sa.Column("priced_count", sa.Integer(), nullable=False),
        # Which trading session the prices came from. snapshot_date is a calendar
        # date, so while the market is shut consecutive days carry the same value
        # -- correctly, since the portfolio really was worth that on each of them.
        # This column is how a chart can say *why* the line is flat rather than
        # leaving it looking like a stalled scraper. NULL when nothing was priced.
        sa.Column("priced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.portfolio_id"],
                                ondelete="CASCADE"),
    )


def downgrade() -> None:
    # Destructive, and in a way f6a7b8c9d0e1's downgrade is not: daily_close and
    # portfolio_snapshots hold the only copy of what they record. Index readings
    # can be re-scraped while cse.lk still serves that session; a portfolio
    # valuation cannot be recomputed at all once the day has passed, because it
    # needs that day's holdings as well as that day's prices.
    op.drop_table("portfolio_snapshots")
    op.drop_table("daily_close")
    op.drop_column("market_data_latest", "last_traded_at")
    op.drop_column("market_data", "last_traded_at")
