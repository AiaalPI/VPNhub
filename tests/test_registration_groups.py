"""Registration must route newcomers to the configured public server pool."""
import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.database.methods.get import get_free_server_id, get_payment_servers, get_person
from bot.database.methods.insert import add_new_person
from bot.database.models.main import Base, Groups, Location, Persons, Servers, Vds
from bot.handlers.user.main import get_first_available_trial_target
from bot.misc.util import CONFIG


@pytest.mark.parametrize('configured_group', ['default', 'public-pool'])
def test_new_registration_can_select_trial_and_paid_server(monkeypatch, configured_group):
    monkeypatch.setattr(CONFIG, 'default_user_group', configured_group)

    async def scenario():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        # Catch missing FK targets, rather than silently accepting invalid groups.
        event.listen(engine.sync_engine, 'connect',
                     lambda connection, _: connection.execute('PRAGMA foreign_keys=ON'))
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add_all([Groups(name=configured_group), Groups(name='private')])
                await session.flush()
                session.add(Location(id=1, name='Public', group=configured_group, work=True))
                await session.flush()
                session.add(Vds(id=1, name='Public', ip='192.0.2.1', location=1,
                                work=True, max_space=500))
                await session.flush()
                session.add(Servers(id=1, vds=1, type_vpn=CONFIG.TypeVpn.VLESS.value,
                                    work=True, auto_work=True, actual_space=55, free_server=False))
                session.add(Persons(tgid=900, group='private'))
                await session.commit()
                await add_new_person(session, SimpleNamespace(id=901, full_name='Test',
                                     language_code='ru'), '@test', None, None)
            # A fresh session verifies the assignment was persisted by registration.
            async with factory() as session:
                person = await get_person(session, 901)
                assert person.group == configured_group
                assert not person.trial_used and not person.keys
                target = await get_first_available_trial_target(session, person)
                assert target == (CONFIG.TypeVpn.VLESS.value, 1)
                server = await get_free_server_id(session, target[1], target[0])
                assert server.id == 1
                assert [s.id for s in await get_payment_servers(session, person.group)] == [1]
                assert (await session.scalar(select(Persons).where(Persons.tgid == 900))).group == 'private'
        finally:
            await engine.dispose()
    asyncio.run(scenario())


@pytest.mark.parametrize('configured_group', ['default', ''])
def test_missing_or_disabled_default_never_assigns_private_group(monkeypatch, configured_group):
    monkeypatch.setattr(CONFIG, 'default_user_group', configured_group)

    async def scenario():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        event.listen(engine.sync_engine, 'connect',
                     lambda connection, _: connection.execute('PRAGMA foreign_keys=ON'))
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with async_sessionmaker(engine)() as session:
                session.add(Groups(name='private'))
                await session.commit()
                await add_new_person(session, SimpleNamespace(id=902, full_name='Test',
                                     language_code=None), '@test', None, None)
                person = await get_person(session, 902)
                assert person.group is None
        finally:
            await engine.dispose()
    asyncio.run(scenario())
