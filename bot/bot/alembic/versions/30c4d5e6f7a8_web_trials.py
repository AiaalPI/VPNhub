"""One-time email trial grants, independent of paid orders."""
from alembic import op
import sqlalchemy as sa

revision = "30c4d5e6f7a8"
down_revision = "20b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("web_trials",
        sa.Column("account_id", sa.String(36), sa.ForeignKey("web_accounts.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("email_digest", sa.String(64), unique=True, nullable=False),
        sa.Column("subscription_id", sa.String(36), sa.ForeignKey("web_subscriptions.id", ondelete="RESTRICT"), unique=True, nullable=False),
        sa.Column("started_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=False))


def downgrade():
    op.drop_table("web_trials")
