from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.utils.constants import WEBAPP_URL
from app.bot.utils.navigation import (
    NavAdminTools,
    NavReferral,
    NavSupport,
)


def main_menu_keyboard(
    is_admin: bool = False,
    is_referral_available: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=_("main_menu:button:open_app"),
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    )

    row = []
    if is_referral_available:
        row.append(
            InlineKeyboardButton(
                text=_("main_menu:button:referral"),
                callback_data=NavReferral.MAIN,
            )
        )
    row.append(
        InlineKeyboardButton(
            text=_("main_menu:button:support"),
            callback_data=NavSupport.MAIN,
        )
    )
    builder.row(*row)

    if is_admin:
        builder.row(
            InlineKeyboardButton(
                text=_("main_menu:button:admin_tools"),
                callback_data=NavAdminTools.MAIN,
            )
        )

    return builder.as_markup()
