import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bot.handlers.user import edit_or_get_key as handler
from bot.misc.callbackData import ChooseLocation
from bot.services import monthly_traffic_service as monthly
from bot.services import shared_subscriptions as shared


def test_optional_accounting_failure_does_not_block_exports(monkeypatch):
    async def scenario():
        session = SimpleNamespace(scalar=AsyncMock(return_value=4))
        reconcile = AsyncMock(side_effect=ValueError('new panel counters below historical baseline'))
        monkeypatch.setattr(monthly, 'reconcile_policy', reconcile)
        await monthly.sync_key_policy(session, 156, required=False)
        with pytest.raises(ValueError):
            await monthly.sync_key_policy(session, 156)
    asyncio.run(scenario())


def test_reselecting_current_vless_server_keeps_identity_and_accounting(monkeypatch):
    monkeypatch.setattr(shared, 'group_for_key', AsyncMock(return_value=None))
    async def scenario():
        server = SimpleNamespace(id=1, type_vpn=1,
            vds_table=SimpleNamespace(location_table=SimpleNamespace(pay_switch=True)))
        key = SimpleNamespace(id=156, user_tgid=123, server=1, server_table=server,
                              switch_location=0, subscription=2000000000, paid_quota_gb=300)
        manager = SimpleNamespace(login=AsyncMock(), get_key=AsyncMock(return_value='vless://stable'),
                                  get_all_user=AsyncMock(return_value=[]))
        call = SimpleNamespace(from_user=SimpleNamespace(id=123),
            message=SimpleNamespace(answer=AsyncMock(return_value=SimpleNamespace(delete=AsyncMock()))),
            answer=AsyncMock())
        monkeypatch.setattr(handler, 'get_lang', AsyncMock(return_value='ru'))
        monkeypatch.setattr(handler, 'get_free_server_id', AsyncMock(return_value=server))
        monkeypatch.setattr(handler, 'get_key_id', AsyncMock(return_value=key))
        monkeypatch.setattr(handler, 'get_name_location_server', AsyncMock(return_value='Helsinki'))
        monkeypatch.setattr(handler, 'ServerManager', lambda *args: manager)
        remove = AsyncMock()
        update = AsyncMock()
        charge = AsyncMock()
        monkeypatch.setattr(handler, 'remove_key_server', remove)
        monkeypatch.setattr(handler, 'update_server_key', update)
        monkeypatch.setattr(handler, 'update_switch_key', charge)
        monkeypatch.setattr(handler, 'server_space_update', AsyncMock())
        delivery = AsyncMock()
        monkeypatch.setattr(handler, 'post_key_telegram', delivery)
        await handler.select_location_callback(call, object(),
            ChooseLocation(id_location=1, key_id=156, type_vpn=1, payment=False), object(), 'remove', object())
        remove.assert_not_awaited()
        update.assert_not_awaited()
        charge.assert_not_awaited()
        manager.get_key.assert_awaited_once()
        assert manager.get_key.await_args.kwargs['limit_gb'] == 300
        delivery.assert_awaited_once()
    asyncio.run(scenario())


def test_export_survives_accounting_rollback_expiring_key(monkeypatch):
    monkeypatch.setattr(shared, 'group_for_key', AsyncMock(return_value=None))
    from bot.services import subscription_service as exports
    async def scenario():
        class Key:
            expired = False
            server = 1
            server_table = SimpleNamespace(id=1)
            user_tgid = 123
            subscription = 2000000000
            paid_quota_gb = 300
            @property
            def id(self):
                assert not self.expired, 'ORM identity accessed after accounting rollback'
                return 7
        key = Key()
        manager = SimpleNamespace(client=object(), login=AsyncMock(),
            get_key=AsyncMock(return_value='vless://stable'), get_fallback_keys=AsyncMock(return_value=[]))
        session = SimpleNamespace(scalar=AsyncMock(return_value=4))
        monkeypatch.setattr(exports, 'get_key_id', AsyncMock(return_value=key))
        monkeypatch.setattr(exports, 'get_name_location_server', AsyncMock(return_value='Helsinki'))
        monkeypatch.setattr(exports, 'ServerManager', lambda *args, **kwargs: manager)
        async def unavailable(*args):
            key.expired = True
            raise ValueError('panel client recreated')
        monkeypatch.setattr(monthly, 'reconcile_policy', unavailable)
        assert await exports.get_clean_marzban_links(session, 7, 123) == ['vless://stable']
        assert manager.get_fallback_keys.await_args.kwargs['key_id'] == 7
    asyncio.run(scenario())
