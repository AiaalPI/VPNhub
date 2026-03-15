"""add_migration_status_to_users

Revision ID: f91b3c2d4a10
Revises: e7b1c4d9a2f6
Create Date: 2026-03-15 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f91b3c2d4a10'
down_revision: Union[str, None] = 'e7b1c4d9a2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists('users', 'migration_status'):
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'migration_status',
                    sa.String(),
                    nullable=True,
                    server_default='none',
                )
            )


def downgrade() -> None:
    if _column_exists('users', 'migration_status'):
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('migration_status')
