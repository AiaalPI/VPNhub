"""Separate email accounts, login challenges, sessions, subscriptions and orders."""
from alembic import op
import sqlalchemy as sa

revision = "10a2b3c4d5e6"
down_revision = "f91b3c2d4a10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("web_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False))
    op.create_table("web_challenges",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False))
    op.create_index("ix_web_challenges_email", "web_challenges", ["email"])
    op.create_index("ix_web_challenges_expires_at", "web_challenges", ["expires_at"])
    op.create_table("web_sessions",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("web_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False))
    op.create_index("ix_web_sessions_account_id", "web_sessions", ["account_id"])
    op.create_index("ix_web_sessions_expires_at", "web_sessions", ["expires_at"])
    op.create_table("web_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("web_accounts.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("client_uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("sub_id", sa.String(32), nullable=False, unique=True),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=False),
        sa.Column("provisioned_until", sa.BigInteger(), nullable=False))
    op.create_table("web_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("web_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subscription_id", sa.String(36), sa.ForeignKey("web_subscriptions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("months", sa.Integer(), nullable=False),
        sa.Column("amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("paid_at", sa.BigInteger()),
        sa.Column("operation_id", sa.String(128), unique=True),
        sa.Column("target_expiry", sa.BigInteger()))
    op.create_index("ix_web_orders_account_id", "web_orders", ["account_id"])


def downgrade():
    for table in ("web_orders", "web_subscriptions", "web_sessions", "web_challenges", "web_accounts"):
        op.drop_table(table)
