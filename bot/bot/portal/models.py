"""Email accounts can explicitly link to a verified Telegram identity."""

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Integer, String

from bot.database.models.main import Base


class WebAccount(Base):
    __tablename__ = "web_accounts"
    id = Column(String(36), primary_key=True)
    email = Column(String(254), unique=True, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    disabled = Column(Boolean, nullable=False, default=False)
    # Historical attribution; no FK so deleting a Telegram account does not erase it.
    referral_tgid = Column(BigInteger, nullable=True, index=True)


class WebChallenge(Base):
    __tablename__ = "web_challenges"
    id = Column(String(64), primary_key=True)
    email = Column(String(254), nullable=False, index=True)
    digest = Column(String(64), nullable=False)
    expires_at = Column(BigInteger, nullable=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    # Freeze the invitation at code issuance, not when another tab changes cookies.
    referral_tgid = Column(BigInteger, nullable=True)


class WebSession(Base):
    __tablename__ = "web_sessions"
    digest = Column(String(64), primary_key=True)
    account_id = Column(String(36), ForeignKey("web_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(BigInteger, nullable=False, index=True)


class WebTelegramLink(Base):
    __tablename__ = "web_telegram_links"
    account_id = Column(String(36), ForeignKey("web_accounts.id", ondelete="CASCADE"), primary_key=True)
    telegram_tgid = Column(BigInteger, ForeignKey("users.tgid", ondelete="CASCADE"), unique=True, nullable=False)
    created_at = Column(BigInteger, nullable=False)


class WebTelegramChallenge(Base):
    __tablename__ = "web_telegram_challenges"
    # Only the digest is persisted; /start tokens never appear in application logs.
    digest = Column(String(64), primary_key=True)
    account_id = Column(String(36), ForeignKey("web_accounts.id", ondelete="CASCADE"), unique=True, nullable=False)
    expires_at = Column(BigInteger, nullable=False)
    telegram_tgid = Column(BigInteger, nullable=True)
    telegram_confirmed_at = Column(BigInteger, nullable=True)
    display_name = Column(String(256), nullable=True)
    username = Column(String(64), nullable=True)
    language = Column(String(16), nullable=True)


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


class SharedSubscription(Base):
    """One entitlement after an explicitly verified website/Telegram link."""
    __tablename__ = 'shared_subscriptions'
    account_id = Column(String(36), ForeignKey('web_accounts.id', ondelete='RESTRICT'), primary_key=True)
    expires_at = Column(BigInteger, nullable=False)
    quota_bytes = Column(BigInteger, nullable=False)
    anchor_at = Column(BigInteger, nullable=False)
    next_reset_at = Column(BigInteger, nullable=False)
    # None: initial counters not captured. -1: unlimited. Zero: exhausted finite.
    allowance_bytes = Column(BigInteger, nullable=True)
    pending_bonus_bytes = Column(BigInteger, nullable=False, default=0)
    merged_at = Column(BigInteger, nullable=False)
    applied_at = Column(BigInteger, nullable=True)


class SharedSubscriptionMember(Base):
    __tablename__ = 'shared_subscription_members'
    policy_id = Column(Integer, ForeignKey('traffic_policies.id', ondelete='RESTRICT'), primary_key=True)
    account_id = Column(String(36), ForeignKey('shared_subscriptions.account_id', ondelete='RESTRICT'), nullable=False, index=True)
    # Immutable pre-merge entitlement used exactly once to preserve remaining GB.
    contributes = Column(Boolean, nullable=False)
    original_quota = Column(BigInteger, nullable=False)
    original_expiry = Column(BigInteger, nullable=False)
    original_reset_at = Column(BigInteger, nullable=False)
    original_upload = Column(BigInteger, nullable=True)
    original_download = Column(BigInteger, nullable=True)
    baseline_upload = Column(BigInteger, nullable=True)
    baseline_download = Column(BigInteger, nullable=True)
    client_uuid = Column(String(36), nullable=True)


class WebAccountMessage(Base):
    """Latest voluntarily opened private Telegram account view."""
    __tablename__ = 'web_account_messages'
    account_id = Column(String(36), ForeignKey('web_accounts.id', ondelete='CASCADE'), primary_key=True)
    telegram_tgid = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=False)
    language = Column(String(16), nullable=False)
    rendered_digest = Column(String(64), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
