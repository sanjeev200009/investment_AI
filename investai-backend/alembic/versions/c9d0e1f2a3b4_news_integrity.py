"""news_sentiment integrity (I-08: real article bodies, dates and attribution)

``news_sentiment`` held 60 rows when this was written. Measured on 2026-08-28,
every one of them was wrong in the same four ways:

  * ``symbol = 'GENERAL'`` on all 60. The scraper wrote
    ``art.get('symbol') or symbol or 'GENERAL'`` where ``symbol`` was the
    scrape function's optional argument, so unless a caller named one specific
    ticker, nothing was ever attributed to anything. The per-symbol sentiment
    endpoint therefore had no rows to read for any of the 293 companies.
  * ``summary`` was the literal string ``'Editorial :'`` on all 60. The
    extractor was ``h3.find_next('p')`` — the next paragraph in document order
    after the headline — which on ft.lk's index page is the footer contact
    block beginning "Editorial : +94 0112 479 356". That string was then fed to
    VADER *as the article text*, and pasted into the dashboard's LLM prompt as
    "recent market news".
  * ``published_at`` NULL on all 60 — never parsed from anywhere.
  * ``sentiment_label`` NULL on all 60.

Three schema changes support the rewrite in ``app/services/news.py``:

**A ``body`` column.** ``summarise_article(headline, body)`` is called from
``analyse_sentiment_batch``, a *separate* Celery task from the scrape, so the
article text has to survive between the two. Without somewhere to put it, either
the summariser re-fetches every article page — a second round of requests to two
publishers for text already read minutes earlier — or it summarises the 500-char
lede, which is summarising a summary. ``summary`` stays the short display string;
``body`` is the input the LLM and VADER score.

**``url`` narrowed from 1000 to 500.** It is half of the unique index below, and
a composite btree key has to stay under Postgres' ~2704-byte limit; at 1000
characters of UTF-8 the planner will not guarantee that. The longest URL across
the 60 existing rows is **151** characters, and both remaining sources use short
slugged paths, so 500 is roughly triple the observed maximum. Article URLs longer
than 500 are rejected at ingest by ``validate_news_record`` rather than silently
truncated to a link that 404s.

**A unique index on (url, symbol).** The table had no unique constraint at all,
so nothing stopped the same story being inserted again on the next 30-minute
beat; it only escaped duplication because the old code re-read the same 20 ft.lk
headlines and inserted them fresh each run — the 60 rows are 20 per source from
a single run. ``(url, symbol)`` rather than ``(url)`` because one article naming
three companies is deliberately three rows, which is what lets
``NewsSentiment.symbol`` stay an indexed equality filter.

The duplicate-collapsing step below is a no-op against current data (0 duplicate
pairs, verified) but is not optional: this migration must also run against
databases where the beat schedule has been up for longer.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""
from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None

# Kept in sync with app.services.news.MAX_URL_LEN and the model's String(500).
URL_LEN = 500


def upgrade() -> None:
    # The full article text, kept so the summariser and the sentiment scorer read
    # what was published rather than the lede or a re-fetch. Text, not String(n):
    # the two sources' stories measured 1,339 and 2,583 characters in probing, but
    # a feature piece has no natural ceiling and truncating prose mid-sentence
    # would corrupt exactly the input the LLM reads.
    op.add_column("news_sentiment", sa.Column("body", sa.Text(), nullable=True))

    # Rows whose URL is longer than the new limit cannot be kept: a truncated URL
    # is a link to nothing, and it would also collide with any sibling sharing the
    # first 500 characters. There are none in current data — this exists so the
    # ALTER below cannot fail with "value too long" on an unknown database.
    op.execute(sa.text(
        f"DELETE FROM news_sentiment WHERE char_length(url) > {URL_LEN}"))

    # Collapse pre-existing duplicates before the unique index is created, keeping
    # the newest row per (url, symbol) — the newest is the one that has been
    # through the most recent pipeline, so it is the one most likely to carry a
    # real body and date.
    op.execute(sa.text("""
        DELETE FROM news_sentiment
        WHERE news_id IN (
            SELECT news_id FROM (
                SELECT news_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY url, symbol
                           ORDER BY scraped_at DESC, news_id DESC) AS rn
                FROM news_sentiment
            ) ranked
            WHERE rn > 1
        )
    """))

    op.alter_column("news_sentiment", "url",
                    existing_type=sa.String(1000),
                    type_=sa.String(URL_LEN),
                    existing_nullable=False)

    # One row per (article, company). The scrape's idempotency depends on this
    # being enforced by the database rather than by the ingest code: the beat runs
    # every 30 minutes over index pages that serve the same stories for hours, so
    # a missed dedupe compounds at 48 runs a day.
    op.create_index("uq_news_url_symbol", "news_sentiment",
                    ["url", "symbol"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_news_url_symbol", table_name="news_sentiment")
    op.alter_column("news_sentiment", "url",
                    existing_type=sa.String(URL_LEN),
                    type_=sa.String(1000),
                    existing_nullable=False)
    op.drop_column("news_sentiment", "body")
