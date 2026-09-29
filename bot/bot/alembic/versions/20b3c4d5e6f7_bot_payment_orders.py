"""Durable bot invoices and retryable payment fulfillment."""
from alembic import op
import sqlalchemy as sa

revision = '20b3c4d5e6f7'
down_revision = '10a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('keys', sa.Column('paid_quota_gb', sa.Integer(), nullable=True))
    op.create_table('bot_payment_orders',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_tgid', sa.BigInteger(), sa.ForeignKey('users.tgid'), nullable=False),
        sa.Column('type_pay', sa.Integer(), nullable=False),
        sa.Column('requested_key_id', sa.Integer(), nullable=True),
        sa.Column('months', sa.Integer(), nullable=False),
        sa.Column('amount_kopecks', sa.Integer(), nullable=False),
        sa.Column('protocol', sa.Integer(), nullable=False),
        sa.Column('location', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('next_attempt', sa.BigInteger(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('operation_id', sa.String(128), unique=True),
        sa.Column('paid_at', sa.BigInteger()),
        sa.Column('key_id', sa.Integer(), sa.ForeignKey('keys.id', ondelete='RESTRICT')),
        sa.Column('bonus_key_id', sa.Integer(), sa.ForeignKey('keys.id', ondelete='SET NULL')),
        sa.Column('bonus_synced', sa.Boolean(), nullable=False),
        sa.Column('fulfilled', sa.Boolean(), nullable=False),
        sa.Column('user_notified', sa.Boolean(), nullable=False),
        sa.Column('admin_notified', sa.Boolean(), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=False),
        sa.Column('last_error', sa.String(80)))
    op.create_index('ix_bot_payment_orders_next_attempt', 'bot_payment_orders', ['next_attempt'])


def downgrade():
    op.drop_table('bot_payment_orders')
    op.drop_column('keys', 'paid_quota_gb')
