"""release hardening: missing users columns, rule dedup column, RLS

Three things a database built from migrations alone was missing:

* ``users.full_name`` and ``users.is_email_verified``. Revision 8a75110865d7 is
  named for them but its body only drops an index; the live database has the
  columns because they were added by hand. Without them every login fails on
  a fresh database. ``IF NOT EXISTS`` keeps this a no-op on the live one.
* ``investment_rules.last_triggered_at`` so rule alerts dedup per rule instead
  of LIKE-matching the symbol inside LLM-written notification text.
* Row-level security on every table in ``public``. Supabase exposes that schema
  through its REST API to anyone holding the anon key, which ships inside the
  mobile app. With RLS on and no policies, those roles see nothing; the backend
  connects as the table owner and is unaffected. The live project already had
  this switched on from the dashboard; this makes a rebuilt one match.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALL_PUBLIC_TABLES = """
    DO $$
    DECLARE t record;
    BEGIN
        FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
            EXECUTE format('ALTER TABLE public.%I {action} ROW LEVEL SECURITY', t.tablename);
        END LOOP;
    END $$;
"""


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS "
               "is_email_verified BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE investment_rules ADD COLUMN IF NOT EXISTS "
               "last_triggered_at TIMESTAMPTZ")
    op.execute(_ALL_PUBLIC_TABLES.replace("{action}", "ENABLE"))


def downgrade() -> None:
    # RLS and the users columns are left in place: removing either would break
    # a database that predates this revision, where they were set by hand.
    op.execute("ALTER TABLE investment_rules DROP COLUMN IF EXISTS last_triggered_at")
