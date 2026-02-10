import os
import sys
import importlib


def test_config_loads():
    env = {
        'ADMIN_TG_ID': '123',
        'TG_TOKEN': 'dummy',
        'NAME': 'vpnbot',
        'CHECK_FOLLOW': '0',
        'LANGUAGES': 'en',
        'PRICE_SWITCH_LOCATION': '10',
        'MONTH_COST': '100',
        'TRIAL_PERIOD': '7',
        'FREE_SWITCH_LOCATION': '1',
        'UTC_TIME': '0',
        'REFERRAL_DAY': '1',
        'REFERRAL_PERCENT': '0',
        'MINIMUM_WITHDRAWAL_AMOUNT': '0',
        'FREE_SERVER': '0',
        'LIMIT_IP': '0',
        'LIMIT_GB': '0',
        'IMPORT_DB': '0',
        'SHOW_DONATE': '0',
        'IS_WORK_EDIT_KEY': '0',
        'POSTGRES_DB': 'testdb',
        'POSTGRES_USER': 'user',
        'POSTGRES_PASSWORD': 'pass',
        'PGADMIN_DEFAULT_EMAIL': 'a@b.com',
        'PGADMIN_DEFAULT_PASSWORD': 'pass',
    }

    os.environ.update(env)

    # Ensure a clean import
    for m in ('bot.misc.util', 'bot.misc', 'bot'):
        sys.modules.pop(m, None)

    mod = importlib.import_module('bot.misc.util')

    assert hasattr(mod, 'CONFIG')
    assert getattr(mod.CONFIG, 'tg_token', None)
