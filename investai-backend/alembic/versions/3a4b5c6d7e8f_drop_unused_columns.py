"""Drop columns nothing reads or writes

Found by the 5 Oct 2026 database audit, each NULL in every row of production:

*   ``users.fcm_token`` -- never on the model or in any migration; push tokens
    live in ``user_profiles.device_token`` since I-12.
*   ``user_profiles.age/occupation/income_level/investment_experience`` -- from
    the initial schema; onboarding saves its answers to ``risk_profiles``.
*   ``chat_messages.context`` -- no caller ever passed a value.

IF EXISTS throughout, so a database that never had ``fcm_token`` migrates too.
The columns hold no data, so downgrade restores them empty.

Revision ID: 3a4b5c6d7e8f
Revises: f2a3b4c5d6e7
"""
from typing import Sequence, Union

from alembic import op

revision: str = '3a4b5c6d7e8f'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = [
    ('users', 'fcm_token', 'TEXT'),
    ('user_profiles', 'age', 'INTEGER'),
    ('user_profiles', 'occupation', 'VARCHAR(120)'),
    ('user_profiles', 'income_level', 'VARCHAR(80)'),
    ('user_profiles', 'investment_experience', 'VARCHAR(80)'),
    ('chat_messages', 'context', 'TEXT'),
]


def upgrade() -> None:
    for table, column, _ in COLUMNS:
        op.execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS {column}')


def downgrade() -> None:
    for table, column, sql_type in COLUMNS:
        op.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {sql_type}')
