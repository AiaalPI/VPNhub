from datetime import datetime

from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Table,
    UniqueConstraint,
    BigInteger
)
from sqlalchemy import Float, DateTime, Boolean

from bot.misc.util import CONFIG

def current_time():
    return datetime.now()

class Base(DeclarativeBase):
    pass


class Groups(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=True)
    locations = relationship('Location', back_populates="group_tabel")
    users = relationship('Persons', back_populates="group_tabel")


class Persons(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    tgid = Column(BigInteger, unique=True)
    banned = Column(Boolean, default=False)
    trial_period = Column(Boolean, default=False)
    trial_used = Column(Boolean, default=False)
    special_offer = Column(Boolean, default=False)
    username = Column(String)
    fullname = Column(String)
    referral_user_tgid = Column(BigInteger, nullable=True)
    referral_balance = Column(Integer, default=0)
    referral_payment_count = Column(Integer, default=0)
    status = Column(Integer, default=0)
    referral_percent = Column(Integer, default=CONFIG.referral_percent)
    lang = Column(String, default=CONFIG.languages)
    lang_tg = Column(String, nullable=True)
    blocked = Column(Boolean, default=False)
    review_bonus_used = Column(Boolean, default=False)
    migration_status = Column(String, default='none')
    date_registered = Column(DateTime, default=current_time)
    trial_activated_at = Column(DateTime, nullable=True)
    trial_expires_at = Column(DateTime, nullable=True)
    group = Column(
        String,
        ForeignKey("groups.name", ondelete='SET NULL'),
        nullable=True)
    metric = Column(
        Integer,
        ForeignKey('metric.id', ondelete='SET NULL'),
        nullable=True
    )
    group_tabel = relationship(Groups, back_populates="users")
    payment = relationship('Payments', back_populates='payment_id')
    metric_rel = relationship("Metric", back_populates="users")
    promocode = relationship(
        'PromoCode',
        secondary='person_promocode_association',
        back_populates='person'
    )
    withdrawal_requests = relationship(
        'WithdrawalRequests',
        back_populates='person'
    )
    keys = relationship(
        'Keys',
        back_populates='person'
    )


class Keys(Base):
    __tablename__ = 'keys'
    id = Column(Integer, primary_key=True, index=True)
    person = relationship(Persons, back_populates="keys")
    user_tgid = Column(BigInteger, ForeignKey("users.tgid"))
    subscription = Column(BigInteger)
    # Absolute purchased allowance; None preserves legacy panel allowance.
    paid_quota_gb = Column(Integer, nullable=True)
    notion_oneday = Column(Boolean, default=False)
    notified_3days = Column(Boolean, default=False)
    notified_1day = Column(Boolean, default=False)
    notified_expired = Column(Boolean, default=False)
    switch_location = Column(Integer, default=0)
    id_payment = Column(String, nullable=True)
    trial_period = Column(Boolean, default=False)
    free_key = Column(Boolean, default=False)
    wg_public_key = Column(String, nullable=True)
    server = Column(
        Integer,
        ForeignKey("servers.id", ondelete='SET NULL'),
        nullable=True)
    server_table = relationship("Servers", back_populates="keys")


class Donate(Base):
    __tablename__ = 'donate'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    price = Column(Float)


class Servers(Base):
    __tablename__ = 'servers'
    id = Column(Integer, primary_key=True, index=True)
    type_vpn = Column(Integer, nullable=False)
    outline_link = Column(String, unique=True)
    ip = Column(String, nullable=True)
    connection_method = Column(Boolean)
    panel = Column(String)
    inbound_id = Column(Integer)
    password = Column(String)
    login = Column(String)
    remnawave_squad_id = Column(String, nullable=True)
    actual_space = Column(Integer, default=0)
    keys = relationship(Keys, back_populates="server_table")
    work = Column(Boolean, default=True)
    auto_work = Column(Boolean, default=True)
    free_server = Column(Boolean, default=False)
    static = relationship("StaticPersons", back_populates="server_table")
    vds = Column(
        Integer,
        ForeignKey("vds.id"),
        nullable=False
    )
    vds_table = relationship('Vds', back_populates="servers")

    @classmethod
    def create_server(cls, data):
        return cls(**data)


class Vds(Base):
    __tablename__ = 'vds'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ip = Column(String, nullable=False, unique=True)
    vds_password = Column(String)
    work = Column(Boolean, default=True)
    max_space = Column(Integer, default=0)
    servers = relationship(Servers, back_populates="vds_table")
    location = Column(
        Integer,
        ForeignKey("location.id"),
        nullable=False
    )
    location_table = relationship('Location', back_populates="vds")

    @classmethod
    def create_vds(cls, data):
        return cls(**data)


class Location(Base):
    __tablename__ = 'location'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    work = Column(Boolean, default=True)
    pay_switch = Column(Boolean, default=False)
    group = Column(
        String,
        ForeignKey("groups.name", ondelete='SET NULL'),
        nullable=True)
    group_tabel = relationship(Groups, back_populates="locations")
    vds = relationship(Vds, back_populates="location_table")

    @classmethod
    def create_location(cls, data):
        return cls(**data)


class Payments(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True, index=True)
    user = Column(Integer, ForeignKey("users.id"))
    payment_id = relationship(Persons, back_populates="payment")
    id_payment = Column(String, nullable=True, unique=True)
    month_count = Column(Integer, nullable=True)
    payment_system = Column(String)
    amount = Column(Float)
    data = Column(DateTime)
    status = Column(String, default='pending')


class ReferralBonus(Base):
    __tablename__ = 'referral_bonuses'
    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(BigInteger, nullable=False, index=True)
    referee_id = Column(BigInteger, nullable=False, index=True)
    bonus_days = Column(Integer, nullable=False, default=3)
    payment_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=current_time, nullable=False)


class StaticPersons(Base):
    __tablename__ = 'static_persons'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    wg_public_key = Column(String, nullable=True)
    server = Column(Integer, ForeignKey("servers.id", ondelete='SET NULL'))
    server_table = relationship("Servers", back_populates="static")


class PromoCode(Base):
    __tablename__ = 'promocode'
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, unique=True, nullable=False)
    percent = Column(Integer, nullable=False)
    type_promo = Column(Integer)
    count_days = Column(Integer, default=None)
    count_use = Column(Integer, nullable=False)
    person = relationship(
        'Persons',
        secondary='person_promocode_association',
        back_populates='promocode',
    )


message_button_association = Table(
    'person_promocode_association',
    Base.metadata,
    Column('promocode_id', Integer, ForeignKey(
        'promocode.id', ondelete='CASCADE'
    )),
    Column('users_id', Integer, ForeignKey(
        'users.id', ondelete='CASCADE'
    )),
    Column('use', Boolean, default=False),
    UniqueConstraint('promocode_id', 'users_id', name='uq_users_promocode')
)


class WithdrawalRequests(Base):
    __tablename__ = 'withdrawal_requests'
    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Integer, nullable=False)
    payment_info = Column(String, nullable=False)
    communication = Column(String)
    check_payment = Column(Boolean, default=False)
    user_tgid = Column(BigInteger, ForeignKey("users.tgid"))
    person = relationship("Persons", back_populates="withdrawal_requests")


class Metric(Base):
    __tablename__ = 'metric'
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String)
    code = Column(String, nullable=False, unique=True)
    users = relationship(Persons, back_populates="metric_rel")


class NotRemoveKey(Base):
    __tablename__ = 'not_remove_key'
    id = Column(Integer, primary_key=True, index=True)
    name_key = Column(String, nullable=False)
    key_id = Column(Integer, nullable=False)
    server_id = Column(Integer, nullable=False)


class BotPaymentOrder(Base):
    """Durable invoice, entitlement and delivery outbox for bot payments."""
    __tablename__ = 'bot_payment_orders'
    id = Column(String(64), primary_key=True)
    user_tgid = Column(BigInteger, ForeignKey('users.tgid'), nullable=False)
    type_pay = Column(Integer, nullable=False)
    requested_key_id = Column(Integer, nullable=True)
    months = Column(Integer, nullable=False)
    amount_kopecks = Column(Integer, nullable=False)
    protocol = Column(Integer, nullable=False)
    location = Column(Integer, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    next_attempt = Column(BigInteger, nullable=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    operation_id = Column(String(128), unique=True, nullable=True)
    paid_at = Column(BigInteger, nullable=True)
    key_id = Column(Integer, ForeignKey('keys.id', ondelete='RESTRICT'), nullable=True)
    bonus_key_id = Column(Integer, ForeignKey('keys.id', ondelete='SET NULL'), nullable=True)
    bonus_synced = Column(Boolean, nullable=False, default=False)
    fulfilled = Column(Boolean, nullable=False, default=False)
    user_notified = Column(Boolean, nullable=False, default=False)
    admin_notified = Column(Boolean, nullable=False, default=False)
    completed = Column(Boolean, nullable=False, default=False)
    last_error = Column(String(80), nullable=True)
