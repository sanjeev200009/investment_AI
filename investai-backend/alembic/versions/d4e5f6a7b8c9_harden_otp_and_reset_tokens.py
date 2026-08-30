"""harden OTP verification and move reset tokens out of process memory

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-27 00:00:00.000000

Why this is needed
------------------
Two independent auth defects, both dormant only while the Supabase sign-in path
went unused, and both live as of the I-02 cutover.

``otp_codes.attempts``
    Verification counted nothing, so a six-digit code — 10^6 possibilities —
    accepted unlimited guesses. That was survivable while Supabase enforced
    email confirmation itself; it is not now that ``/auth/verify-otp`` is the
    only thing between registration and a confirmed account. The column is
    ``NOT NULL DEFAULT 0`` so codes already in flight when this runs are treated
    as having no guesses spent rather than as exhausted.

``password_reset_tokens``
    Reset tokens lived in ``app/utils/security.py`` as a module-level dict. Every
    pending reset was lost on restart, no sibling worker could see a token minted
    by another (so with more than one uvicorn worker or Railway replica a reset
    failed roughly whenever the second request landed elsewhere), and nothing
    ever expired, so the dict grew for the lifetime of the process.

    Postgres rather than Redis: Redis is a hard dependency of the Celery workers
    but not of the API, which touches it on no request path. Storing reset state
    there would add a new runtime dependency to the API and make password reset
    fail whenever Redis is down. The database is already required to serve any
    request, and ``otp_codes`` established this pattern for the same kind of
    credential.

    Only a SHA-256 hash of the token is stored (64 hex chars, hence the width).
    The raw token is returned to the caller once and never persisted, so read
    access to this table yields nothing that can be redeemed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "otp_codes",
        sa.Column("attempts", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Unique: the lookup key. A duplicate hash must not be able to shadow a live
    # token, and verification deletes by this column.
    op.create_index("ix_password_reset_tokens_token_hash",
                    "password_reset_tokens", ["token_hash"], unique=True)
    # Non-unique: create_reset_token deletes prior tokens for an address, so this
    # supports that sweep. Not unique, because that delete and the insert are
    # separate statements and a brief overlap must not raise.
    op.create_index("ix_password_reset_tokens_email",
                    "password_reset_tokens", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_email",
                  table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_token_hash",
                  table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("otp_codes", "attempts")
