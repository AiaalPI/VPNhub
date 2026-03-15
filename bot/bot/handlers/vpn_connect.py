from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from nats.js import JetStreamContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.user.keys_user import handle_vpn_connect_click

vpn_connect_router = Router()


@vpn_connect_router.callback_query(F.data == "vpn_connect_btn")
async def vpn_connect_click(
    call: CallbackQuery,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    state: FSMContext,
) -> None:
    # Single integration point for "Подключить VPN" button.
    await handle_vpn_connect_click(
        call=call,
        session=session,
        js=js,
        remove_key_subject=remove_key_subject,
        state=state,
    )

