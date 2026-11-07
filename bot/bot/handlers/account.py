"""Telegram view of the same email account and its current subscriptions."""
import time
import hashlib
import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fastapi import HTTPException
from sqlalchemy import select

from bot.misc.callbackData import DetailKey
from bot.misc.language import Localization, get_lang
from bot.portal import accounts, services
from bot.portal.config import PortalConfig
from bot.portal.models import WebSubscription, WebAccountMessage
from bot.portal.subscriptions import subscription_url

account_router = Router()
_ = Localization.text


async def handle_link_start(message, session, payload: str | None) -> bool:
    if not payload or not payload.startswith(accounts.LINK_PREFIX):
        return False
    lang = "en" if message.from_user.language_code == "en" else "ru"
    if message.chat.type != "private":
        return True
    try:
        if not PortalConfig.from_env().enabled:
            raise HTTPException(404)
        token = payload[len(accounts.LINK_PREFIX):]
        email = await accounts.claim_link(session, token, message.from_user)
        kb = InlineKeyboardBuilder()
        kb.button(text=_("portal_link_yes", lang), callback_data="pl_yes:" + token)
        kb.button(text=_("portal_link_no", lang), callback_data="pl_no:" + token)
        kb.adjust(1)
        await message.answer(_("portal_link_prompt", lang).format(email=email),
                             reply_markup=kb.as_markup(), parse_mode=None)
        return True
    except HTTPException:
        text = _("portal_link_error", lang)
    await message.answer(text)
    return True


@account_router.callback_query(F.data.startswith("pl_yes:"))
@account_router.callback_query(F.data.startswith("pl_no:"))
async def confirm_link_callback(call, session):
    await call.answer()
    lang = "en" if call.from_user.language_code == "en" else "ru"
    cancel = call.data.startswith("pl_no:")
    try:
        await accounts.approve_link(session, call.data.split(":", 1)[1], call.from_user.id, cancel=cancel)
        text = _("portal_link_cancelled" if cancel else "portal_link_return", lang)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            # A repeated callback may arrive after its keyboard was removed.
            pass
    except HTTPException:
        text = _("portal_link_error", lang)
    await call.message.answer(text)


async def active_web_subscription(session, telegram_id: int):
    if not PortalConfig.from_env().enabled:
        return None
    user = await accounts.linked_account(session, telegram_id)
    if not user:
        return None
    return await session.scalar(select(WebSubscription).where(
        WebSubscription.account_id == user.id, WebSubscription.expires_at > int(time.time())))


async def account_view(session, telegram_id: int, lang: str):
    cfg = PortalConfig.from_env()
    if not cfg.enabled:
        return _("portal_unavailable", lang), None
    user = await accounts.linked_account(session, telegram_id)
    kb = InlineKeyboardBuilder()
    kb.button(text=_("portal_open_website", lang), url=cfg.origin + "/web/#account")
    text = _("portal_link_from_website", lang)
    if user:
        try:
            state = await accounts.snapshot(session, user)
        except HTTPException:
            return _("portal_link_error", lang), None
        sub = await session.scalar(select(WebSubscription).where(WebSubscription.account_id == user.id))
        text = _("portal_account_title", lang)
        if sub and sub.expires_at:
            expires = datetime.fromtimestamp(sub.expires_at, timezone.utc).strftime("%d.%m.%Y")
            text += "\n" + _("portal_shared_subscription" if state.get('shared_subscription') else "portal_subscription", lang).format(
                date=expires, quota=(_('unlimited_traffic_label', lang) if sub.quota_bytes == 0 else str(sub.quota_bytes // 1073741824) + ' ' + _('traffic_gb_unit', lang)))
            if sub.expires_at > time.time() and sub.provisioned_until >= sub.expires_at:
                kb.button(text=_("portal_profiles", lang), callback_data="portal_profiles")
            elif sub.expires_at > time.time():
                text += "\n" + _("portal_pending", lang)
        for key in state["telegram_subscriptions"][:20]:
            expires = datetime.fromtimestamp(key["expires_at"], timezone.utc).strftime("%d.%m.%Y")
            text += "\n" + _("portal_telegram_key", lang).format(key=key["id"], date=expires)
            if key["active"]:
                kb.button(text=_("portal_telegram_key_button", lang).format(key=key["id"]),
                          callback_data=DetailKey(key_id=key["id"]))
        text += "\n\n" + _("portal_history", lang).format(count=len(state["history"]))
        for order in state["history"][:5]:
            date = datetime.fromtimestamp(order["created_at"], timezone.utc).strftime("%d.%m.%Y")
            text += "\n" + _("portal_history_row", lang).format(
                date=date, amount=f'{order["amount_kopecks"] / 100:.2f}')
    kb.button(text=_("back_general_menu_btn", lang), callback_data="back_general_menu_btn")
    kb.adjust(1)
    return text, kb.as_markup()


def view_digest(text, keyboard):
    return hashlib.sha256((text + (keyboard.model_dump_json() if keyboard else '')).encode()).hexdigest()


async def show_account(message, session, telegram_id: int, lang: str) -> None:
    text, keyboard = await account_view(session, telegram_id, lang)
    sent = await message.answer(text, reply_markup=keyboard)
    # Never track a group chat or a synthetic/mock message as a private view.
    if not isinstance(getattr(sent, 'message_id', None), int) or getattr(getattr(sent, 'chat', None), 'id', None) != telegram_id:
        return
    user = await accounts.linked_account(session, telegram_id)
    if user:
        from bot.services.shared_subscriptions import lock_account
        await lock_account(session, account_id=user.id)
        row = await session.get(WebAccountMessage, user.id)
        if row is None:
            row = WebAccountMessage(account_id=user.id)
            session.add(row)
        row.telegram_tgid, row.message_id, row.language = telegram_id, sent.message_id, lang
        row.rendered_digest, row.active = view_digest(text, keyboard), True
        await session.flush()


async def refresh_account_message(bot, session, account_id):
    """Edit the existing private view; never send unsolicited new messages."""
    row = await session.get(WebAccountMessage, account_id)
    if bot is None or row is None or not row.active:
        return
    user = await accounts.linked_account(session, row.telegram_tgid)
    if user is None or user.id != account_id:
        return
    text, keyboard = await account_view(session, row.telegram_tgid, row.language)
    digest = view_digest(text, keyboard)
    if digest == row.rendered_digest:
        return
    try:
        await bot.edit_message_text(text, chat_id=row.telegram_tgid, message_id=row.message_id, reply_markup=keyboard)
    except TelegramBadRequest as exc:
        if 'message is not modified' not in str(exc).lower():
            row.active = False
    row.rendered_digest = digest
    await session.commit()


async def try_refresh_account_message(bot, session, account_id):
    try:
        await refresh_account_message(bot, session, account_id)
    except Exception as exc:
        await session.rollback()
        logging.getLogger(__name__).warning('event=account_view_refresh_failed reason=%s', type(exc).__name__)


@account_router.message(Command("account"))
async def account_command(message, session, state):
    await show_account(message, session, message.from_user.id,
                       await get_lang(session, message.from_user.id, state))


@account_router.callback_query(F.data == "portal_account")
async def account_callback(call, session, state):
    await call.answer()
    await show_account(call.message, session, call.from_user.id,
                       await get_lang(session, call.from_user.id, state))


@account_router.callback_query(F.data == "portal_profiles")
async def profile_callback(call, session, state):
    await call.answer()
    lang = await get_lang(session, call.from_user.id, state)
    sub = await active_web_subscription(session, call.from_user.id)
    if not sub or sub.provisioned_until < sub.expires_at:
        await call.message.answer(_("portal_pending", lang))
        return
    try:
        # Read-only panel access: expiration/renewal stays in the same web row.
        links = await services.panel_access(session, sub)
    except Exception:
        await call.message.answer(_("portal_profiles_error", lang))
        return
    url = subscription_url(sub)
    if url:
        await call.message.answer(url, parse_mode=None)
        return
    for link in links:
        await call.message.answer(link, parse_mode=None)
