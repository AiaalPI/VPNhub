"""add_ref_user

Revision ID: ba7a3ffb8d04
Revises: e7152afbe174
Create Date: 2025-05-08 17:20:43.565948

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'ba7a3ffb8d04'
down_revision: Union[str, None] = 'e7152afbe174'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Return True if *column* already exists in *table* (Postgres + SQLite safe)."""
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists('users', 'status'):
        op.add_column('users', sa.Column('status', sa.Integer(), nullable=True))
    if not _column_exists('users', 'referral_percent'):
        op.add_column('users', sa.Column('referral_percent', sa.Integer(), nullable=True))


def downgrade() -> None:
    if _column_exists('users', 'referral_percent'):
        op.drop_column('users', 'referral_percent')
    if _column_exists('users', 'status'):
        op.drop_column('users', 'status')
