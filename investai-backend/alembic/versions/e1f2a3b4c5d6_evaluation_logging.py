"""evaluation logging: daily recommendation snapshots and lesson views

Both tables exist only to measure the evaluation plan: recommendation accuracy
(E5) and lesson engagement (E7). RLS is enabled like every other public table.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recommendation_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('risk_category', sa.String(20), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('model_version', sa.String(30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('snapshot_date', 'risk_category', 'symbol', name='uq_rec_snapshot_day_cat_symbol'),
    )
    op.create_index('ix_recommendation_snapshots_snapshot_date', 'recommendation_snapshots', ['snapshot_date'])
    op.create_table(
        'lesson_views',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('lesson_id', sa.String(60), nullable=False),
        sa.Column('viewed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_lesson_views_user_id', 'lesson_views', ['user_id'])
    op.execute("ALTER TABLE public.recommendation_snapshots ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.lesson_views ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table('lesson_views')
    op.drop_table('recommendation_snapshots')
