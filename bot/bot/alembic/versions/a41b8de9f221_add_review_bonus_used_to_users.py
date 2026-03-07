"""add_review_bonus_used_to_users

Revision ID: a41b8de9f221
Revises: 9d2f1a7b4c11
Create Date: 2026-03-06 18:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'a41b8de9f221'
down_revision: Union[str, None] = '9d2f1a7b4c11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists('users', 'review_bonus_used'):
        op.add_column(
            'users',
            sa.Column(
                'review_bonus_used',
                sa.Boolean(),
                nullable=True,
                server_default=sa.false()
            )
        )


def downgrade() -> None:
    if _column_exists('users', 'review_bonus_used'):
        op.drop_column('users', 'review_bonus_used')
