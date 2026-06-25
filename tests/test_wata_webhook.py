import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def wata_env():
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
        self.headers = {"X-Signature": "signature"}
        self.app = SimpleNamespace(state=SimpleNamespace(http_client=AsyncMock()))

    async def body(self):
        return b"{}"


def _install_prometheus_stub():
    sys.modules["prometheus_client"] = SimpleNamespace(
        CONTENT_TYPE_LATEST="text/plain",
        Counter=lambda *args, **kwargs: SimpleNamespace(labels=lambda *a, **k: SimpleNamespace(inc=lambda *x, **y: None)),
        Histogram=lambda *args, **kwargs: SimpleNamespace(labels=lambda *a, **k: SimpleNamespace(observe=lambda *x, **y: None)),
        generate_latest=lambda: b"",
    )


@pytest.mark.asyncio
async def test_wata_webhook_skips_duplicate_transaction(
    wata_env,
    cleanup_bot_modules,
):
    os.environ.clear()
    os.environ.update(wata_env)
    _install_prometheus_stub()

    from bot.webhooks.hook_wata import wata_webhook

    webhook_data = {
        "transactionStatus": "Paid",
        "transactionId": "tx-123",
        "orderId": "1/new_key/0/7/1/5/123",
        "amount": "100.00",
    }
    webhook_module = MagicMock()
    webhook_module.process_webhook = AsyncMock(return_value=webhook_data)

    with patch("bot.webhooks.hook_wata.WebhookModule", return_value=webhook_module):
        with patch("bot.webhooks.hook_wata.get_payment", new=AsyncMock(return_value=object()), create=True):
            with patch("bot.webhooks.hook_wata.PaymentSystem") as payment_system:
                response = await wata_webhook(DummyRequest())

    assert response.status_code == 200
    payment_system.assert_not_called()
