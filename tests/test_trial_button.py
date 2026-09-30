"""Exercise the actual tariff button through trial key creation."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, func, event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.database.models.main import Base, Groups, Location, Vds, Servers, Persons, Keys
from bot.database.methods.get import get_person
from bot.handlers.user import keys_user
from bot.keyboards.inline.user_inline import renew
from bot.misc.callbackData import TrialPeriod
from bot.misc.util import CONFIG


@pytest.mark.parametrize('scenario', ['direct', 'location', 'full', 'offline', 'private', 'wrong_protocol', 'missing'])
def test_tariff_trial_button(monkeypatch, scenario):
    async def run():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        event.listen(engine.sync_engine, 'connect',
                     lambda connection, _: connection.execute('PRAGMA foreign_keys=ON'))
        panel = SimpleNamespace(login=AsyncMock(), get_key=AsyncMock(return_value='vless://test'),
                                get_all_user=AsyncMock(return_value=[SimpleNamespace()]))
        # Only panel I/O and Telegram delivery are mocked.
        monkeypatch.setattr(keys_user, 'ServerManager', lambda server: panel)
        delivery = AsyncMock()
        monkeypatch.setattr(keys_user, 'post_key_telegram', delivery)
        monkeypatch.setattr(keys_user, 'get_lang', AsyncMock(return_value='ru'))
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                session.add_all([Groups(name='default'), Groups(name='private')])
                await session.flush()
                session.add(Location(id=11, name='Test', work=True,
                                     group='private' if scenario == 'private' else 'default'))
                await session.flush()
                session.add(Vds(id=1, name='Test', ip='192.0.2.1', location=11, work=True,
                                max_space=1 if scenario == 'full' else 500))
                await session.flush()
                session.add(Servers(id=7, type_vpn=1, vds=1, actual_space=1,
                                    work=True, auto_work=scenario != 'offline', free_server=False))
                session.add(Persons(tgid=901, group='default', banned=True, trial_used=False))
                await session.commit()
                location = 11 if scenario == 'location' else (-999 if scenario == 'missing' else -7)
                protocol = 2 if scenario == 'wrong_protocol' else 1
                keyboard = await renew(CONFIG, 'ru', CONFIG.type_payment[0], 'back_general_menu_btn',
                                       trial_flag=False, id_protocol=protocol, id_location=location)
                packed = next(b.callback_data for row in keyboard.inline_keyboard for b in row
                              if (b.callback_data or '').startswith('trial_period:'))
                callback = TrialPeriod.unpack(packed)
                message = SimpleNamespace(answer=AsyncMock(return_value=SimpleNamespace(delete=AsyncMock())),
                                          answer_photo=AsyncMock(), delete=AsyncMock())
                call = SimpleNamespace(message=message, from_user=SimpleNamespace(id=901), answer=AsyncMock())
                await keys_user.choose_server_user(call, session, AsyncMock(), callback)
                person = await get_person(session, 901)
                count = await session.scalar(select(func.count(Keys.id)))
                if scenario in ('direct', 'location'):
                    assert person.trial_used and person.trial_period
                    assert count == 1
                    key = await session.scalar(select(Keys))
                    assert key.server == 7 and key.trial_period
                    panel.get_key.assert_awaited_once()
                    assert panel.get_key.await_args.kwargs['key_id'] == key.id
                    delivery.assert_awaited_once()
                    # A repeated callback must not grant a second trial or key.
                    await keys_user.choose_server_user(call, session, AsyncMock(), callback)
                    assert await session.scalar(select(func.count(Keys.id))) == 1
                    assert panel.get_key.await_count == 1
                else:
                    assert count == 0 and not person.trial_used and not person.trial_period
                    panel.login.assert_not_awaited()
                    delivery.assert_not_awaited()
                    message.answer.assert_awaited_once()
                message.delete.assert_not_awaited()
                message.answer_photo.assert_not_awaited()
        finally:
            await engine.dispose()
    asyncio.run(run())
