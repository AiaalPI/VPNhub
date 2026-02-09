import os
from enum import Enum
from typing import List

from dotenv import load_dotenv

load_dotenv()


def parse_csv_urls(value: str) -> List[str]:
    """Parse comma-separated URLs into a list, ignoring empty items.

    Empty or None input returns an empty list.
    """
    if value is None:
        return []
    # split and strip; ignore empty strings
    parts = [p.strip() for p in value.split(',') if p.strip()]
    return parts


class Config:
    admin_tg_id: int
    month_cost: List[int]
    auto_extension: bool = False
    trial_period: int
    UTC_time: int
    max_people_server: int
    limit_ip: int
    limit_GB: int
    tg_token: str
    yoomoney_token: str
    yoomoney_wallet_token: str
    lava_token_secret: str
    lava_id_project: str
    yookassa_shop_id: str
    yookassa_secret_key: str
    cryptomus_key: str
    cryptomus_uuid: str
    wawa_token_card: str
    wawa_token_sbp: str
    wawa_token_visa: str
    referral_day: int
    referral_percent: int
    minimum_withdrawal_amount: int
    COUNT_SECOND_DAY: int = 86400
    COUNT_SECOND_MOTH: int = 2678400
    languages: str
    name: str
    # channel fields (types fixed)
    id_channel: int | None = None
    link_channel: str = ''
    name_channel: str = ''
    crypto_bot_api: str = ''
    debug: bool = False
    postgres_db: str
    postgres_user: str
    postgres_password: str
    max_count_groups: int = 100
    import_bd: int = 0
    check_follow: bool = False
    token_stars: str
    heleket_key: str
    heleket_uuid: str
    type_payment: dict = {
        0: 'new_key',
        1: 'extend_key',
        2: 'donate',
        3: 'switch'
    }
    type_buttons_mailing: list = [
        'vpn_connect_btn',
        'donate_btn',
        'language_btn',
        'help_btn',
        'promokod_btn',
        'affiliate_btn',
        'about_vpn_btn',
        'general_menu_btn',
        'not_button_mailing_btn'
    ]
    free_switch_location: int
    price_switch_location_type: int
    free_vpn: int
    limit_gb_free: int
    font_template: str = ''
    show_donate: bool
    is_work_edit_key: bool
    # nats servers as list; default matches docker-compose
    nats_servers: List[str] = ['nats://nats:4222']
    nats_remove_consumer_subject: str = 'aiogram.remove.key'
    nats_remove_consumer_stream: str = 'DeleteKeyStream'
    nats_remove_consumer_durable_name: str = 'remove_key_consumer'
    delay_remove_key: int = 300
    alert_server_space: int = 20
    # server check protections
    server_check_timeout_sec: int = 8
    server_check_concurrency: int = 5

    class TypeVpn(Enum):
        OUTLINE = 0
        VLESS = 1
        SHADOW_SOCKS = 2
        WIREGUARD = 3
        AMNEZIA_WG = 4
        TROJAN = 5
        REMNAWAVE = 6

    def __init__(self):
        self.read_evn()

    def is_admin(self, id_user) -> bool:
        return id_user == self.admin_tg_id

    def read_evn(self):
        admin_id = os.getenv('ADMIN_TG_ID')
        if admin_id == '':
            raise ValueError('Write your ID Telegram to ADMIN_TG_ID')
        self.admin_tg_id = int(admin_id)

        self.tg_token = os.getenv('TG_TOKEN')
        if self.tg_token is None:
            raise ValueError('Write your TOKEN TelegramBot to TG_TOKEN')

        self.name = os.getenv('NAME')
        if self.name is None:
            raise ValueError('Write your name bot to NAME')

        check_follow = os.getenv('CHECK_FOLLOW')
        if check_follow == '':
            raise ValueError('Write your check follow to CHECK_FOLLOW')
        self.check_follow = bool(int(check_follow))

        id_channel_env = os.getenv('ID_CHANNEL')
        if self.check_follow and id_channel_env == '':
            raise ValueError('Write your ID channel to ID_CHANNEL')
        # if provided, convert to int
        if id_channel_env not in (None, ''):
            self.id_channel = int(id_channel_env)

        self.link_channel = os.getenv('LINK_CHANNEL') or ''
        if self.check_follow and self.link_channel == '':
            raise ValueError('Write your link channel to LINK_CHANNEL')

        self.name_channel = os.getenv('NAME_CHANNEL') or ''
        if self.check_follow and self.name_channel == '':
            raise ValueError('Write your name channel to NAME_CHANNEL')

        self.languages = os.getenv('LANGUAGES')
        if self.languages is None:
            raise ValueError('Write your languages bot to LANGUAGES')

        price_switch_location_type = os.getenv('PRICE_SWITCH_LOCATION')
        if price_switch_location_type is None:
            raise ValueError(
                'Enter the price for changing '
                'the key location PRICE_SWITCH_LOCATION'
            )
        self.price_switch_location_type = int(price_switch_location_type)

        try:
            month_cost_val = os.getenv('MONTH_COST')
            if month_cost_val in (None, ''):
                raise ValueError('Write your price month to MONTH_COST')
            # parse into list[int]
            parts = [p.strip() for p in month_cost_val.split(',') if p.strip()]
            self.month_cost = [int(p) for p in parts]
        except Exception as e:
            raise ValueError('You filled in the MONTH_COST field incorrectly') from e

        trial_period = os.getenv('TRIAL_PERIOD')
        if trial_period == '':
            raise ValueError(
                'Write your time trial period sec to TRIAL_PERIOD'
            )
        self.trial_period = int(trial_period)

        free_switch_location = os.getenv('FREE_SWITCH_LOCATION')
        if free_switch_location == '':
            raise ValueError(
                'Write your free swith location min 1 FREE_SWITCH_LOCATION'
            )
        if int(free_switch_location) <= 0:
            raise ValueError(
                'Write your free swith location min 1 FREE_SWITCH_LOCATION'
            )
        self.free_switch_location = int(free_switch_location)

        utc_time = os.getenv('UTC_TIME')
        if utc_time == '':
            raise ValueError('Write your UTC TIME to UTC_TIME')
        self.UTC_time = int(utc_time)

        referral_day = os.getenv('REFERRAL_DAY')
        if referral_day == '':
            raise ValueError('Write your day per referral to REFERRAL_DAY')
        self.referral_day = int(referral_day)

        referral_percent = os.getenv('REFERRAL_PERCENT')
        if referral_percent == '':
            raise ValueError(
                'Write your percent per referral to REFERRAL_PERCENT'
            )
        self.referral_percent = int(referral_percent)

        minimum_withdrawal_amount = os.getenv('MINIMUM_WITHDRAWAL_AMOUNT')
        if minimum_withdrawal_amount == '':
            raise ValueError(
                'Write your minimum withdrawal amount to '
                'MINIMUM_WITHDRAWAL_AMOUNT'
            )
        self.minimum_withdrawal_amount = int(minimum_withdrawal_amount)

        free_vpn = os.getenv('FREE_SERVER')
        if free_vpn == '':
            raise ValueError('Write your FREE_SERVER')
        self.free_vpn = int(free_vpn)

        limit_gb_free = os.getenv('LIMIT_GB_FREE')
        if self.free_vpn and limit_gb_free == '':
            raise ValueError('Write your limit gb free server LIMIT_GB_FREE')
        self.limit_gb_free = int(limit_gb_free)

        limit_ip = os.getenv('LIMIT_IP')
        self.limit_ip = int(limit_ip if limit_ip != '' else 0)

        limit_gb = os.getenv('LIMIT_GB')
        self.limit_GB = int(limit_gb if limit_gb != '' else 0)

        import_bd = os.getenv('IMPORT_DB')
        self.import_bd = int(import_bd if import_bd != '' else 0)

        show_donate = os.getenv('SHOW_DONATE')
        if show_donate == '':
            raise ValueError('Write your SHOW_DONATE')
        self.show_donate = bool(int(show_donate))

        is_work_edit_key = os.getenv('IS_WORK_EDIT_KEY')
        if is_work_edit_key == '':
            raise ValueError('Write your IS_WORK_EDIT_KEY')
        self.is_work_edit_key = bool(int(is_work_edit_key))

        token_stars = os.getenv('TG_STARS')
        self.token_stars = '' if token_stars != 'off' else token_stars
        token_stars = os.getenv('TG_STARS_DEV')
        self.token_stars = '' if token_stars == 'run' else self.token_stars

        self.yoomoney_token = os.getenv('YOOMONEY_TOKEN', '')
        self.yoomoney_wallet_token = os.getenv('YOOMONEY_WALLET', '')
        self.lava_token_secret = os.getenv('LAVA_TOKEN_SECRET', '')
        self.lava_id_project = os.getenv('LAVA_ID_PROJECT', '')
        self.yookassa_shop_id = os.getenv('YOOKASSA_SHOP_ID', '')
        self.yookassa_secret_key = os.getenv('YOOKASSA_SECRET_KEY', '')
        self.cryptomus_key = os.getenv('CRYPTOMUS_KEY', '')
        self.cryptomus_uuid = os.getenv('CRYPTOMUS_UUID', '')
        self.heleket_key = os.getenv('HELEKET_KEY', '')
        self.heleket_uuid = os.getenv('HELEKET_UUID', '')
        self.crypto_bot_api = os.getenv('CRYPTO_BOT_API', '')
        self.wawa_token_card = os.getenv('WATA_TOKEN_CARD', '')
        self.wawa_token_sbp = os.getenv('WATA_TOKEN_SBP', '')
        self.wawa_token_visa = os.getenv('WATA_TOKEN_VISA', '')
        self.font_template = os.getenv('FONT_TEMPLATE', '')
        self.debug = os.getenv('DEBUG') == 'True'
        self.postgres_db = os.getenv('POSTGRES_DB', '')
        if self.postgres_db == '':
            raise ValueError('Write your name DB to POSTGRES_DB')
        self.postgres_user = os.getenv('POSTGRES_USER', '')
        if self.postgres_user == '':
            raise ValueError('Write your login DB to POSTGRES_USER')
        self.postgres_password = os.getenv('POSTGRES_PASSWORD', '')
        if self.postgres_password == '':
            raise ValueError('Write your password DB to POSTGRES_PASSWORD')
        pg_email = os.getenv('PGADMIN_DEFAULT_EMAIL', '')
        if pg_email == '':
            raise ValueError('Write your email to PGADMIN_DEFAULT_EMAIL')
        pg_password = os.getenv('PGADMIN_DEFAULT_PASSWORD', '')
        if pg_password == '':
            raise ValueError('Write your password to PGADMIN_DEFAULT_PASSWORD')

        # NATS: prefer NATS_SERVERS (comma-separated list), fallback to legacy NATS_URL
        nats_servers_env = os.getenv('NATS_SERVERS')
        nats_url_env = os.getenv('NATS_URL')
        parsed = parse_csv_urls(nats_servers_env) if nats_servers_env not in (None, '') else []
        if parsed:
            self.nats_servers = parsed
        elif nats_url_env not in (None, ''):
            # legacy single URL fallback
            self.nats_servers = [nats_url_env]
        else:
            # keep default
            self.nats_servers = ['nats://nats:4222']

        # Server checks config: allow empty string to be treated as not set
        timeout_env = os.getenv('SERVER_CHECK_TIMEOUT_SEC')
        if timeout_env not in (None, ''):
            try:
                val = int(timeout_env)
            except Exception:
                raise ValueError('Invalid SERVER_CHECK_TIMEOUT_SEC')
            if val <= 0:
                raise ValueError('SERVER_CHECK_TIMEOUT_SEC must be > 0')
            self.server_check_timeout_sec = val

        concurrency_env = os.getenv('SERVER_CHECK_CONCURRENCY')
        if concurrency_env not in (None, ''):
            try:
                val = int(concurrency_env)
            except Exception:
                raise ValueError('Invalid SERVER_CHECK_CONCURRENCY')
            if val <= 0:
                raise ValueError('SERVER_CHECK_CONCURRENCY must be > 0')
            self.server_check_concurrency = val


CONFIG = Config()
