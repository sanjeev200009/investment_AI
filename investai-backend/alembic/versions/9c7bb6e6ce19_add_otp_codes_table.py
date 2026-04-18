"""add_otp_codes_table

Revision ID: 9c7bb6e6ce19
Revises: 79fcf139c76e
Create Date: 2026-04-18 17:24:37.504111

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c7bb6e6ce19'
down_revision: Union[str, None] = '79fcf139c76e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('otp_codes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(), nullable=False, index=True),
        sa.Column('otp_code', sa.String(6), nullable=False),
        sa.Column('purpose', sa.String(), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default='false'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()')),
    )
    op.create_index('idx_otp_email_purpose', 
                    'otp_codes', ['email', 'purpose'])

def downgrade() -> None:
    op.drop_index('idx_otp_email_purpose', 'otp_codes')
    op.drop_table('otp_codes')
