from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.routers.misc.keyboard import back_button, back_to_main_menu_button
from app.bot.utils.navigation import NavSupport


def contact_button(support_id: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=_("support:button:contact"), url=f"tg://user?id={support_id}")


def support_keyboard(support_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text=_("support:button:install_ios"), callback_data=NavSupport.INSTALL_IOS),
        InlineKeyboardButton(text=_("support:button:install_android"), callback_data=NavSupport.INSTALL_ANDROID),
    )
    builder.row(
        InlineKeyboardButton(text=_("support:button:telegram_proxy"), callback_data=NavSupport.TELEGRAM_PROXY),
        InlineKeyboardButton(text=_("support:button:whatsapp_proxy"), callback_data=NavSupport.WHATSAPP_PROXY),
    )
    builder.row(
        InlineKeyboardButton(text=_("support:button:vpn_not_working"), callback_data=NavSupport.VPN_NOT_WORKING),
    )
    builder.row(contact_button(support_id))
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def topic_keyboard(support_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(contact_button(support_id))
    builder.row(back_button(NavSupport.MAIN))
    return builder.as_markup()
