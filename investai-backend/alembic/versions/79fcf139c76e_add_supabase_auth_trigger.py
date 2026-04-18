"""add_supabase_auth_trigger

Revision ID: 79fcf139c76e
Revises: c7df033a746c
Create Date: 2026-04-18 16:33:30.131358

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79fcf139c76e'
down_revision: Union[str, None] = 'c7df033a746c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
