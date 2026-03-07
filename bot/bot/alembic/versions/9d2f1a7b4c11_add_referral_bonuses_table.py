"""add_referral_bonuses_table

Revision ID: 9d2f1a7b4c11
Revises: f3a1c9e82b05
Create Date: 2026-03-06 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '9d2f1a7b4c11'
down_revision: Union[str, None] = 'f3a1c9e82b05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    if not _table_exists('referral_bonuses'):
        op.create_table(
            'referral_bonuses',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('referrer_id', sa.BigInteger(), nullable=False),
            sa.Column('referee_id', sa.BigInteger(), nullable=False),
            sa.Column('bonus_days', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('payment_id', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(
            op.f('ix_referral_bonuses_id'),
            'referral_bonuses',
            ['id'],
            unique=False
        )
        op.create_index(
            op.f('ix_referral_bonuses_referrer_id'),
            'referral_bonuses',
            ['referrer_id'],
            unique=False
        )
        op.create_index(
            op.f('ix_referral_bonuses_referee_id'),
            'referral_bonuses',
            ['referee_id'],
            unique=False
        )


def downgrade() -> None:
    if _table_exists('referral_bonuses'):
        op.drop_index(op.f('ix_referral_bonuses_referee_id'), table_name='referral_bonuses')
        op.drop_index(op.f('ix_referral_bonuses_referrer_id'), table_name='referral_bonuses')
        op.drop_index(op.f('ix_referral_bonuses_id'), table_name='referral_bonuses')
        op.drop_table('referral_bonuses')
