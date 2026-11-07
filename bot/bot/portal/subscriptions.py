"""Cookie-independent, revocable website subscriptions for VPN applications."""
import asyncio
import logging
import re
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from bot.database.models.main import Servers, TrafficPolicy
from bot.misc.util import CONFIG
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.VPN.Xui.Vless import Vless
from bot.portal import accounts, services
from bot.portal.config import PortalConfig
from bot.portal.models import WebAccount, WebSubscription
from bot.services.clash_subscription_service import build_clash_config
from bot.services.singbox_subscription_service import build_singbox_config
from bot.services.subscription_headers import subscription_profile_headers
from bot.services.subscription_usage_service import usage_from_global_clients

router = APIRouter(prefix='/subscriptions/web', include_in_schema=False)
log = logging.getLogger(__name__)


def subscription_url(sub) -> str | None:
    if not CONFIG.public_subscription_base:
        return None
    return f'{CONFIG.public_subscription_base}/subscriptions/web/{sub.sub_id}'


async def web_usage(session, sub):
    manager = None
    try:
        async with asyncio.timeout(6):
            from bot.portal.models import SharedSubscription
            from bot.services.shared_subscriptions import usage
            if await session.get(SharedSubscription, sub.account_id):
                return await usage(session, sub.account_id)
            server = await session.get(Servers, sub.server_id)
            if server is None:
                return None
            manager = ServerManager(server, timeout=4)
            if not isinstance(manager.client, Vless):
                return None
            await manager.login()
            response = await manager.client.xui.request(method='GET', endpoint='/panel/api/clients/list')
            usage = usage_from_global_clients(response, 'web.' + sub.id)
            policy = await session.scalar(select(TrafficPolicy).where(TrafficPolicy.web_subscription_id == sub.id))
            from bot.services.monthly_traffic_service import monthly_usage
            return monthly_usage(usage, policy)
    except Exception as exc:
        log.warning('event=web_subscription_accounting_unavailable reason=%s', type(exc).__name__)
        return None
    finally:
        try:
            if manager is not None and isinstance(manager.client, Vless):
                await manager.client.xui.close()
        except Exception as exc:
            log.warning('event=web_subscription_panel_close_failed reason=%s', type(exc).__name__)


async def owned_public_subscription(request, token):
    cfg = getattr(request.app.state, 'portal_config', None) or PortalConfig.from_env()
    if not cfg.enabled or not re.fullmatch('[0-9a-f]{32}', token):
        raise HTTPException(403, 'invalid_subscription_token')
    session = request.state.session
    sub = await session.scalar(select(WebSubscription).where(WebSubscription.sub_id == token))
    user = await session.get(WebAccount, sub.account_id) if sub else None
    if not user or user.disabled or sub.expires_at <= int(time.time()):
        raise HTTPException(403, 'invalid_subscription_token')
    await accounts.linked_person(session, user.id)
    if sub.provisioned_until < sub.expires_at:
        raise HTTPException(503, 'subscription_provisioning_pending', headers={'Retry-After': '30'})
    return sub


@router.get('/{token}')
@router.get('/{token}/{format}')
async def public_subscription(token: str, request: Request, format: str = 'vless'):
    if format not in ('vless', 'clash', 'singbox'):
        raise HTTPException(404)
    sub = await owned_public_subscription(request, token)
    try:
        links = await services.panel_access(request.state.session, sub)
    except Exception:
        raise HTTPException(503, 'subscription_temporarily_unavailable') from None
    payload = '\n'.join(links)
    media_type = 'text/plain'
    if format == 'clash':
        payload, media_type = build_clash_config(links), 'text/yaml'
    elif format == 'singbox':
        payload, media_type = build_singbox_config(links), 'application/json'
    if not payload:
        raise HTTPException(404, 'no_parseable_profiles')
    usage = await web_usage(request.state.session, sub)
    return PlainTextResponse(payload, media_type=media_type,
        headers=subscription_profile_headers(expire_ts=sub.expires_at,
            content_disposition='inline; filename="kyn-vpn.txt"', usage=usage))
