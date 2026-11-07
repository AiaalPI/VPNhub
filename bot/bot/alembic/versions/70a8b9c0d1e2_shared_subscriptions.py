"""Shared entitlements; existing identities and receipt history remain intact."""
from alembic import op
import sqlalchemy as sa

revision = '70a8b9c0d1e2'
down_revision = '60f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('shared_subscriptions',
        sa.Column('account_id', sa.String(36), sa.ForeignKey('web_accounts.id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('expires_at', sa.BigInteger(), nullable=False),
        sa.Column('quota_bytes', sa.BigInteger(), nullable=False),
        sa.Column('anchor_at', sa.BigInteger(), nullable=False),
        sa.Column('next_reset_at', sa.BigInteger(), nullable=False),
        sa.Column('allowance_bytes', sa.BigInteger()),
        sa.Column('pending_bonus_bytes', sa.BigInteger(), nullable=False),
        sa.Column('merged_at', sa.BigInteger(), nullable=False),
        sa.Column('applied_at', sa.BigInteger()))
    op.create_table('shared_subscription_members',
        sa.Column('policy_id', sa.Integer(), sa.ForeignKey('traffic_policies.id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('shared_subscriptions.account_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('contributes', sa.Boolean(), nullable=False),
        sa.Column('original_quota', sa.BigInteger(), nullable=False),
        sa.Column('original_expiry', sa.BigInteger(), nullable=False),
        sa.Column('original_reset_at', sa.BigInteger(), nullable=False),
        sa.Column('original_upload', sa.BigInteger()),
        sa.Column('original_download', sa.BigInteger()),
        sa.Column('baseline_upload', sa.BigInteger()),
        sa.Column('baseline_download', sa.BigInteger()),
        sa.Column('client_uuid', sa.String(36)))
    op.create_index('ix_shared_subscription_members_account_id', 'shared_subscription_members', ['account_id'])
    op.create_table('web_account_messages',
        sa.Column('account_id', sa.String(36), sa.ForeignKey('web_accounts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('telegram_tgid', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('language', sa.String(16), nullable=False),
        sa.Column('rendered_digest', sa.String(64), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False))


def downgrade():
    # Financial merges cannot be reversed by dropping schema: preserved source
    # expiries already represent the common entitlement. Require recovery plan.
    raise RuntimeError('Shared entitlements require an explicit data recovery migration')
