"""add_status_to_payments

Revision ID: d4c9e1b2a7f0
Revises: b62d8b21e9a7, c8b1d5f0e3a4
Create Date: 2026-03-10 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'd4c9e1b2a7f0'
down_revision: Union[str, tuple[str, str], None] = (
    'b62d8b21e9a7',
    'c8b1d5f0e3a4',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists('payments', 'status'):
        with op.batch_alter_table('payments', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'status',
                    sa.String(),
                    nullable=True,
                    server_default='pending'
                )
            )


def downgrade() -> None:
    if _column_exists('payments', 'status'):
        with op.batch_alter_table('payments', schema=None) as batch_op:
            batch_op.drop_column('status')
