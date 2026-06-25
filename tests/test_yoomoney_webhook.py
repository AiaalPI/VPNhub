import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def yoomoney_env():
    return {
        "ADMIN_TG_ID": "123",
        "TG_TOKEN": "test_token",
        "NAME": "testbot",
        "CHECK_FOLLOW": "0",
        "LANGUAGES": "en,ru",
        "PRICE_SWITCH_LOCATION": "10",
        "MONTH_COST": "100,200,300,400",
        "TRIAL_PERIOD": "604800",
        "FREE_SWITCH_LOCATION": "1",
        "UTC_TIME": "0",
        "REFERRAL_DAY": "1",
        "REFERRAL_PERCENT": "10",
        "MINIMUM_WITHDRAWAL_AMOUNT": "100",
        "FREE_SERVER": "0",
        "LIMIT_IP": "0",
        "LIMIT_GB": "0",
        "IMPORT_DB": "0",
        "SHOW_DONATE": "1",
        "IS_WORK_EDIT_KEY": "1",
        "POSTGRES_DB": "testdb",
        "POSTGRES_USER": "testuser",
        "POSTGRES_PASSWORD": "testpass",
        "PGADMIN_DEFAULT_EMAIL": "admin@test.com",
        "PGADMIN_DEFAULT_PASSWORD": "adminpass",
        "YOOMONEY_WEBHOOK_TOKEN": "",
    }


@pytest.fixture
def cleanup_bot_modules():
    for module_name in list(sys.modules.keys()):
        if module_name.startswith("bot"):
            del sys.modules[module_name]
    yield
    for module_name in list(sys.modules.keys()):
        if module_name.startswith("bot"):
            del sys.modules[module_name]


class DummyRequest:
    def __init__(self):
        self.state = SimpleNamespace(
            session=AsyncMock(),
            bot=AsyncMock(),
            request_id="test-request",
        )
        self.headers = {"content-type": "application/json"}
        self.url = SimpleNamespace(path="/payments/yoomoney/webhook")

    async def body(self):
        return b"{}"


@pytest.mark.asyncio
async def test_yoomoney_webhook_rejects_when_shared_secret_is_not_configured(
    yoomoney_env,
    cleanup_bot_modules,
):
    os.environ.clear()
    os.environ.update(yoomoney_env)
    sys.modules["prometheus_client"] = SimpleNamespace(
        CONTENT_TYPE_LATEST="text/plain",
        Counter=lambda *args, **kwargs: SimpleNamespace(labels=lambda *a, **k: SimpleNamespace(inc=lambda *x, **y: None)),
        Histogram=lambda *args, **kwargs: SimpleNamespace(labels=lambda *a, **k: SimpleNamespace(observe=lambda *x, **y: None)),
        generate_latest=lambda: b"",
    )

    from bot.webhooks.hook_yoomoney import _handle_yoomoney_webhook

    response = await _handle_yoomoney_webhook(DummyRequest())

    assert response.status_code == 403
