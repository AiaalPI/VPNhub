import os
import sys
import importlib


BASE_ENV = {
    "ADMIN_TG_ID": "123",
    "TG_TOKEN": "dummy",
    "NAME": "vpnbot",
    "CHECK_FOLLOW": "0",
    "LANGUAGES": "en",
    "PRICE_SWITCH_LOCATION": "10",
    "MONTH_COST": "100",          # у тебя это list[int], но строкой "100" ок
    "TRIAL_PERIOD": "7",
    "FREE_SWITCH_LOCATION": "1",
    "UTC_TIME": "0",
    "REFERRAL_DAY": "1",
    "REFERRAL_PERCENT": "0",
    "MINIMUM_WITHDRAWAL_AMOUNT": "0",
    "FREE_SERVER": "0",
    "LIMIT_IP": "0",
    "LIMIT_GB": "0",
    "IMPORT_DB": "0",
    "SHOW_DONATE": "0",
    "IS_WORK_EDIT_KEY": "0",
    "POSTGRES_DB": "testdb",
    "POSTGRES_USER": "user",
    "POSTGRES_PASSWORD": "pass",
    "PGADMIN_DEFAULT_EMAIL": "a@b.com",
    "PGADMIN_DEFAULT_PASSWORD": "pass",
    # важно: когда FREE_SERVER=0, LIMIT_GB_FREE не обязателен
}


def _reload_util_with_env(extra_env: dict):
    # чистим импорты, чтобы CONFIG пересоздался
    for m in ("bot.misc.util", "bot.misc", "bot"):
        sys.modules.pop(m, None)

    # гарантируем чистоту NATS переменных между тестами
    os.environ.pop("NATS_SERVERS", None)
    os.environ.pop("NATS_URL", None)

    env = dict(BASE_ENV)
    env.update(extra_env)
    os.environ.update(env)

    return importlib.import_module("bot.misc.util")


def test_nats_servers_parsing():
    mod = _reload_util_with_env(
        {
            "NATS_SERVERS": "nats://127.0.0.1:4222, nats://nats:4222,,  nats://10.0.0.2:4222 ",
        }
    )
    assert mod.CONFIG.nats_servers == [
        "nats://127.0.0.1:4222",
        "nats://nats:4222",
        "nats://10.0.0.2:4222",
    ]


def test_nats_url_fallback():
    mod = _reload_util_with_env({"NATS_URL": "nats://fallback:4222"})
    assert mod.CONFIG.nats_servers == ["nats://fallback:4222"]