"""Keep the Telegram inviter when a guest chooses email registration."""
from alembic import op
import sqlalchemy as sa

revision = "40d5e6f7a8b9"
down_revision = "30c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("web_accounts", sa.Column("referral_tgid", sa.BigInteger(), nullable=True))
    op.create_index("ix_web_accounts_referral_tgid", "web_accounts", ["referral_tgid"])
    op.add_column("web_challenges", sa.Column("referral_tgid", sa.BigInteger(), nullable=True))


def downgrade():
    op.drop_column("web_challenges", "referral_tgid")
    op.drop_index("ix_web_accounts_referral_tgid", table_name="web_accounts")
    op.drop_column("web_accounts", "referral_tgid")
