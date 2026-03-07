"""add_trial_used_and_notification_flags

Revision ID: b62d8b21e9a7
Revises: a41b8de9f221
Create Date: 2026-03-06 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = 'b62d8b21e9a7'
down_revision: Union[str, None] = 'a41b8de9f221'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists('users', 'trial_used'):
        op.add_column(
            'users',
            sa.Column(
                'trial_used',
                sa.Boolean(),
                nullable=True,
                server_default=sa.false(),
            )
        )

    if not _column_exists('keys', 'notified_1day'):
        op.add_column(
            'keys',
            sa.Column(
                'notified_1day',
                sa.Boolean(),
                nullable=True,
                server_default=sa.false(),
            )
        )

    if not _column_exists('keys', 'notified_expired'):
        op.add_column(
            'keys',
            sa.Column(
                'notified_expired',
                sa.Boolean(),
                nullable=True,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    if _column_exists('keys', 'notified_expired'):
        op.drop_column('keys', 'notified_expired')
    if _column_exists('keys', 'notified_1day'):
        op.drop_column('keys', 'notified_1day')
    if _column_exists('users', 'trial_used'):
        op.drop_column('users', 'trial_used')
