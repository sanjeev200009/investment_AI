"""add risk_profiles.answers to retain the wizard responses

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-26 00:00:00.000000

Why this is needed
------------------
``risk_profiles`` stored only the derived ``score`` and ``category``. The
fifteen answers that produced them were discarded, which had two costs:

*   The score could not be audited or recomputed. If the scoring weights in
    app/services/risk_scoring.py are ever revised — likely, since the
    instrument is part of the project's evaluation — existing users' scores
    could not be recalculated without asking them to retake the assessment.
*   Two of the wizard's questions are collected for reasons other than risk
    scoring and were being thrown away regardless: Q13 (sector interest, feeds
    recommendation filtering) and Q14 (preferred language, feeds the
    multilingual response requirement).

JSONB rather than a set of typed columns because the instrument's shape belongs
to risk_scoring.py, not to the schema; pinning fifteen answers to fifteen
columns would mean a migration every time a question is reworded.

The column is nullable: any profile written before this revision has no stored
answers, and the API treats that as "unknown" rather than "empty".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "risk_profiles",
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("risk_profiles", "answers")
