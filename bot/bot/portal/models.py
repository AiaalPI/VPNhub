"""Portal identities are separate from Telegram users and their lifecycle jobs."""

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Integer, String

from bot.database.models.main import Base


class WebAccount(Base):
    __tablename__ = "web_accounts"
    id = Column(String(36), primary_key=True)
    email = Column(String(254), unique=True, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    disabled = Column(Boolean, nullable=False, default=False)


class WebChallenge(Base):
    __tablename__ = "web_challenges"
    id = Column(String(64), primary_key=True)
    email = Column(String(254), nullable=False, index=True)
    digest = Column(String(64), nullable=False)
    expires_at = Column(BigInteger, nullable=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)


class WebSession(Base):
    __tablename__ = "web_sessions"
    digest = Column(String(64), primary_key=True)
    account_id = Column(String(36), ForeignKey("web_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(BigInteger, nullable=False, index=True)


class WebSubscription(Base):
    __tablename__ = "web_subscriptions"
    id = Column(String(36), primary_key=True)
    account_id = Column(String(36), ForeignKey("web_accounts.id", ondelete="CASCADE"), unique=True, nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="RESTRICT"), nullable=False)
    client_uuid = Column(String(36), unique=True, nullable=False)
    sub_id = Column(String(32), unique=True, nullable=False)
    expires_at = Column(BigInteger, nullable=False, default=0)
    quota_bytes = Column(BigInteger, nullable=False, default=0)
    provisioned_until = Column(BigInteger, nullable=False, default=0)


class WebOrder(Base):
    __tablename__ = "web_orders"
    id = Column(String(36), primary_key=True)
    account_id = Column(String(36), ForeignKey("web_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    subscription_id = Column(String(36), ForeignKey("web_subscriptions.id", ondelete="RESTRICT"), nullable=False)
    months = Column(Integer, nullable=False)
    amount_kopecks = Column(Integer, nullable=False)
    quota_bytes = Column(BigInteger, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    paid_at = Column(BigInteger, nullable=True)
    operation_id = Column(String(128), unique=True, nullable=True)
    # Absolute entitlement is persisted before talking to the panel; retries
    # never add the purchased duration twice.
    target_expiry = Column(BigInteger, nullable=True)


class WebTrial(Base):
    """Durable one-time grant; panel retries must never grant another trial."""
    __tablename__ = "web_trials"
    account_id = Column(String(36), ForeignKey("web_accounts.id", ondelete="RESTRICT"), primary_key=True)
    email_digest = Column(String(64), unique=True, nullable=False)
    subscription_id = Column(String(36), ForeignKey("web_subscriptions.id", ondelete="RESTRICT"), unique=True, nullable=False)
    started_at = Column(BigInteger, nullable=False)
    expires_at = Column(BigInteger, nullable=False)
    quota_bytes = Column(BigInteger, nullable=False)
