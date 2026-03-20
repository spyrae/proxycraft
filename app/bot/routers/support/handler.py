import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _

from app.bot.utils.navigation import NavSupport
from app.config import Config
from app.db.models import User

from .keyboard import support_keyboard, topic_keyboard

logger = logging.getLogger(__name__)
router = Router(name=__name__)


@router.callback_query(F.data == NavSupport.MAIN)
async def callback_support(callback: CallbackQuery, user: User, config: Config) -> None:
    logger.info(f"User {user.tg_id} opened support page.")
    await callback.answer()
    await callback.message.edit_text(
        text=_("support:message:main"),
        reply_markup=support_keyboard(),
    )


@router.callback_query(F.data == NavSupport.INSTALL_IOS)
async def callback_install_ios(callback: CallbackQuery, user: User, config: Config) -> None:
    logger.info(f"User {user.tg_id} opened install iOS page.")
    await callback.answer()
    await callback.message.edit_text(
        text=_("support:message:install_ios"),
        reply_markup=topic_keyboard(),
    )


@router.callback_query(F.data == NavSupport.INSTALL_ANDROID)
async def callback_install_android(callback: CallbackQuery, user: User, config: Config) -> None:
    logger.info(f"User {user.tg_id} opened install Android page.")
    await callback.answer()
    await callback.message.edit_text(
        text=_("support:message:install_android"),
        reply_markup=topic_keyboard(),
    )


@router.callback_query(F.data == NavSupport.TELEGRAM_PROXY)
async def callback_telegram_proxy(callback: CallbackQuery, user: User, config: Config) -> None:
    logger.info(f"User {user.tg_id} opened Telegram proxy page.")
    await callback.answer()
    await callback.message.edit_text(
        text=_("support:message:telegram_proxy"),
        reply_markup=topic_keyboard(),
    )


@router.callback_query(F.data == NavSupport.WHATSAPP_PROXY)
async def callback_whatsapp_proxy(callback: CallbackQuery, user: User, config: Config) -> None:
    logger.info(f"User {user.tg_id} opened WhatsApp proxy page.")
    await callback.answer()
    await callback.message.edit_text(
        text=_("support:message:whatsapp_proxy"),
        reply_markup=topic_keyboard(),
    )


@router.callback_query(F.data == NavSupport.VPN_NOT_WORKING)
async def callback_vpn_not_working(callback: CallbackQuery, user: User, config: Config) -> None:
    logger.info(f"User {user.tg_id} opened VPN not working page.")
    await callback.answer()
    await callback.message.edit_text(
        text=_("support:message:vpn_not_working"),
        reply_markup=topic_keyboard(),
    )
