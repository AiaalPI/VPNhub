"""add_unique_constraint_payments_id_payment

Revision ID: e7b1c4d9a2f6
Revises: d4c9e1b2a7f0
Create Date: 2026-03-10 10:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'e7b1c4d9a2f6'
down_revision: Union[str, None] = 'd4c9e1b2a7f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _unique_exists(table: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(
        uc.get("name") == constraint_name
        for uc in insp.get_unique_constraints(table)
    )


def upgrade() -> None:
    name = 'uq_payments_id_payment'
    if not _unique_exists('payments', name):
        with op.batch_alter_table('payments', schema=None) as batch_op:
            batch_op.create_unique_constraint(name, ['id_payment'])


def downgrade() -> None:
    name = 'uq_payments_id_payment'
    if _unique_exists('payments', name):
        with op.batch_alter_table('payments', schema=None) as batch_op:
            batch_op.drop_constraint(name, type_='unique')
