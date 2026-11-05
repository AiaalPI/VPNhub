"""Durable calendar-month traffic allowance policies."""
from alembic import op
import sqlalchemy as sa

revision = '60f7a8b9c0d1'
down_revision = '50e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('traffic_policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('server_id', sa.Integer(), sa.ForeignKey('servers.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('email', sa.String(128), nullable=False),
        sa.Column('key_id', sa.Integer(), sa.ForeignKey('keys.id', ondelete='CASCADE'), unique=True),
        sa.Column('web_subscription_id', sa.String(36), sa.ForeignKey('web_subscriptions.id', ondelete='CASCADE'), unique=True),
        sa.Column('months', sa.Integer(), nullable=False),
        sa.Column('quota_gb', sa.Integer(), nullable=False),
        sa.Column('anchor_at', sa.BigInteger(), nullable=False),
        sa.Column('next_reset_at', sa.BigInteger(), nullable=False),
        sa.Column('baseline_upload', sa.BigInteger()),
        sa.Column('baseline_download', sa.BigInteger()),
        sa.Column('panel_limit_bytes', sa.BigInteger()),
        sa.Column('applied_at', sa.BigInteger()),
        sa.UniqueConstraint('server_id', 'email', name='uq_traffic_policy_client'))


def downgrade():
    op.drop_table('traffic_policies')
