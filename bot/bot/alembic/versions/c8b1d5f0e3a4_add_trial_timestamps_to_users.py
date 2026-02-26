"""add_trial_timestamps_to_users

Revision ID: c8b1d5f0e3a4
Revises: a2be5439f125
Create Date: 2026-02-11 19:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'c8b1d5f0e3a4'
down_revision: Union[str, None] = 'a2be5439f125'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Return True if *column* already exists in *table* (Postgres + SQLite safe)."""
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        if not _column_exists('users', 'trial_activated_at'):
            batch_op.add_column(sa.Column('trial_activated_at', sa.TIMESTAMP(timezone=False), nullable=True))
        if not _column_exists('users', 'trial_expires_at'):
            batch_op.add_column(sa.Column('trial_expires_at', sa.TIMESTAMP(timezone=False), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        if _column_exists('users', 'trial_expires_at'):
            batch_op.drop_column('trial_expires_at')
        if _column_exists('users', 'trial_activated_at'):
            batch_op.drop_column('trial_activated_at')
