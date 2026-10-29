"""Link confirmed email and Telegram identities without moving entitlements."""
from alembic import op
import sqlalchemy as sa

revision = "50e6f7a8b9c0"
down_revision = "40d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("web_telegram_links",
        sa.Column("account_id", sa.String(36), sa.ForeignKey("web_accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("telegram_tgid", sa.BigInteger(), sa.ForeignKey("users.tgid", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False))
    op.create_table("web_telegram_challenges",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("web_accounts.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("telegram_tgid", sa.BigInteger()),
        sa.Column("telegram_confirmed_at", sa.BigInteger()),
        sa.Column("display_name", sa.String(256)),
        sa.Column("username", sa.String(64)),
        sa.Column("language", sa.String(16)))


def downgrade():
    op.drop_table("web_telegram_challenges")
    op.drop_table("web_telegram_links")
