from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.utils.constants import WEBAPP_URL
from app.bot.utils.navigation import (
    NavAdminTools,
    NavMTProto,
    NavProfile,
    NavReferral,
    NavSubscription,
    NavSupport,
    NavWhatsApp,
)


def main_menu_keyboard(
    is_admin: bool = False,
    is_referral_available: bool = False,
    is_trial_available: bool = False,
    is_referred_trial_available: bool = False,
    is_mtproto_enabled: bool = False,
    is_whatsapp_enabled: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if is_referred_trial_available:
        builder.row(
            InlineKeyboardButton(
                text=_("referral:button:get_referred_trial"),
                callback_data=NavReferral.GET_REFERRED_TRIAL,
            )
        )
    elif is_trial_available:
        builder.row(
            InlineKeyboardButton(
                text=_("subscription:button:get_trial"), callback_data=NavSubscription.GET_TRIAL
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=_("main_menu:button:profile"),
            callback_data=NavProfile.MAIN,
        ),
        InlineKeyboardButton(
            text=_("main_menu:button:subscription"),
            callback_data=NavSubscription.MAIN,
        ),
    )
    if is_mtproto_enabled:
        builder.row(
            InlineKeyboardButton(
                text=_("main_menu:button:mtproto"),
                callback_data=NavMTProto.MAIN,
            )
        )
    if is_whatsapp_enabled:
        builder.row(
            InlineKeyboardButton(
                text=_("main_menu:button:whatsapp"),
                callback_data=NavWhatsApp.MAIN,
            )
        )

    builder.row(
        *(
            [
                InlineKeyboardButton(
                    text=_("main_menu:button:referral"),
                    callback_data=NavReferral.MAIN,
                )
            ]
            if is_referral_available
            else []
        ),
        InlineKeyboardButton(
            text=_("main_menu:button:support"),
            callback_data=NavSupport.MAIN,
        ),
    )

    builder.row(
        InlineKeyboardButton(
            text=_("main_menu:button:open_app"),
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    )

    if is_admin:
        builder.row(
            InlineKeyboardButton(
                text=_("main_menu:button:admin_tools"),
                callback_data=NavAdminTools.MAIN,
            )
        )

    return builder.as_markup()
