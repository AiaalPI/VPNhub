"""add_referral_payment_count

Revision ID: f3a1c9e82b05
Revises: ba7a3ffb8d04
Create Date: 2026-03-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f3a1c9e82b05'
down_revision: Union[str, None] = 'ba7a3ffb8d04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Return True if *column* already exists in *table* (Postgres + SQLite safe)."""
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists('users', 'referral_payment_count'):
        op.add_column(
            'users',
            sa.Column('referral_payment_count', sa.Integer(), nullable=True, server_default='0')
        )


def downgrade() -> None:
    if _column_exists('users', 'referral_payment_count'):
        op.drop_column('users', 'referral_payment_count')
