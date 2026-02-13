"""add_trial_timestamps_to_users

Revision ID: c8b1d5f0e3a4
Revises: a2be5439f125
Create Date: 2026-02-11 19:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8b1d5f0e3a4'
down_revision: Union[str, None] = 'a2be5439f125'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trial_activated_at', sa.TIMESTAMP(timezone=False), nullable=True))
        batch_op.add_column(sa.Column('trial_expires_at', sa.TIMESTAMP(timezone=False), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('trial_expires_at')
        batch_op.drop_column('trial_activated_at')
