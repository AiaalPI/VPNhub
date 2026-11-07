import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select

from bot.misc.util import CONFIG
from bot.portal import services, subscriptions
from bot.portal.models import WebAccount, WebSubscription
from bot.services.subscription_usage_service import SubscriptionUsage
from test_web_portal import environment, login


def inbound(network='tcp', port=443):
    return {'port': port, 'streamSettings': {'network': network, 'security': 'reality',
        'xhttpSettings': {'path': '/kept', 'mode': 'auto'},
        'realitySettings': {'serverNames': ['example.com'], 'shortIds': ['abcdef'],
            'settings': {'publicKey': 'public-key', 'fingerprint': 'chrome'}}}}


def test_both_website_profile_transports_use_public_map_without_changing_identity(monkeypatch):
    monkeypatch.setattr(CONFIG, 'xui_public_addresses', {1: '89.125.136.14'})
    sub = SimpleNamespace(client_uuid='11111111-1111-4111-8111-111111111111')
    server = SimpleNamespace(id=1, connection_method=True, ip='private-panel.example:2053/path')
    for network, port in [('tcp',443),('xhttp',2087)]:
        p=urlsplit(services._client_link(sub, server, inbound(network,port)))
        assert (p.username,p.hostname,p.port)==(sub.client_uuid,'89.125.136.14',port)
        assert parse_qs(p.query)['pbk']==['public-key']
    assert server.ip=='private-panel.example:2053/path'
    server.id=2
    assert urlsplit(services._client_link(sub,server,inbound())).hostname=='private-panel.example'


def test_public_url_survives_renewal_and_revocation_is_effective(monkeypatch):
    async def scenario():
        engine,factory,app,client,sent=await environment(monkeypatch)
        app.include_router(subscriptions.router)
        monkeypatch.setattr(CONFIG,'public_subscription_base','https://sub.example.test:8443')
        monkeypatch.setattr(services,'panel_access',AsyncMock(return_value=[
            services._client_link(SimpleNamespace(client_uuid='11111111-1111-4111-8111-111111111111'),
                SimpleNamespace(id=1,ip='198.51.100.1',connection_method=True),inbound())]))
        monkeypatch.setattr(subscriptions,'web_usage',AsyncMock(return_value=SubscriptionUsage(123,456,300*1073741824)))
        token='a'*32
        try:
            await login(client,sent)
            async with factory() as session:
                account=await session.scalar(select(WebAccount))
                sub=WebSubscription(id='sub-id',account_id=account.id,server_id=1,
                    client_uuid='11111111-1111-4111-8111-111111111111',sub_id=token,
                    expires_at=int(time.time())+86400,provisioned_until=int(time.time())+86401,quota_bytes=300*1073741824)
                session.add(sub);await session.commit()
            payload=(await client.get('/web/api/subscription')).json()
            assert payload['subscription_url'].endswith('/subscriptions/web/'+token)
            # VPN app does not have the browser's authenticated cookie.
            client.cookies.clear()
            for suffix in ('','/clash','/singbox'):
                r=await client.get('/subscriptions/web/'+token+suffix)
                assert r.status_code==200,r.text
                assert r.headers['cache-control']=='no-store'
                assert 'total=322122547200' in r.headers['subscription-userinfo']
            async with factory() as session:
                sub=await session.get(WebSubscription,'sub-id')
                sub.expires_at+=86400;sub.provisioned_until=sub.expires_at
                expected=sub.expires_at;await session.commit()
            r=await client.get('/subscriptions/web/'+token)
            assert f'expire={expected}' in r.headers['subscription-userinfo']
            subscriptions.web_usage.return_value=None
            r=await client.get('/subscriptions/web/'+token)
            assert r.status_code==200 and 'subscription-userinfo' not in r.headers
            async with factory() as session:
                sub=await session.get(WebSubscription,'sub-id');sub.sub_id='b'*32;await session.commit()
            assert (await client.get('/subscriptions/web/'+token)).status_code==403
            assert (await client.get('/subscriptions/web/'+'b'*32)).status_code==200
            async with factory() as session:
                sub=await session.get(WebSubscription,'sub-id');sub.expires_at=1;await session.commit()
            assert (await client.get('/subscriptions/web/'+'b'*32)).status_code==403
            assert (await client.get('/subscriptions/web/not-a-token')).status_code==403
        finally:
            await client.aclose();await engine.dispose()
    asyncio.run(scenario())
