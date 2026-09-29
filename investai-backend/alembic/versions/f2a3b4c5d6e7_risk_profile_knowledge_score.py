"""risk_profiles.knowledge_score: result of the onboarding knowledge checks

The onboarding quiz became a 15-stop journey: ten profile questions and five
beginner knowledge checks. The server marks the checks (0-5) and keeps the
result here; GET /me/plan orders a beginner's first steps from it. Nullable:
profiles from the older quiz have no knowledge result.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE risk_profiles ADD COLUMN IF NOT EXISTS knowledge_score INTEGER')


def downgrade() -> None:
    op.execute('ALTER TABLE risk_profiles DROP COLUMN IF EXISTS knowledge_score')
