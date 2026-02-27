from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.models.whatsapp_data import WhatsAppData
from app.bot.routers.misc.keyboard import back_to_main_menu_button, close_notification_button
from app.bot.utils.navigation import NavWhatsApp


def whatsapp_main_keyboard(
    has_subscription: bool,
    callback_data: WhatsAppData,
    is_trial_available: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if has_subscription:
        builder.row(
            InlineKeyboardButton(
                text=_("whatsapp:button:show_info"),
                callback_data=NavWhatsApp.SHOW_INFO,
            )
        )
        callback_data.state = NavWhatsApp.EXTEND
        callback_data.is_extend = True
        builder.row(
            InlineKeyboardButton(
                text=_("whatsapp:button:extend"),
                callback_data=callback_data.pack(),
            )
        )
    else:
        callback_data.state = NavWhatsApp.BUY
        builder.row(
            InlineKeyboardButton(
                text=_("whatsapp:button:buy"),
                callback_data=callback_data.pack(),
            )
        )
        if is_trial_available:
            builder.row(
                InlineKeyboardButton(
                    text=_("whatsapp:button:trial"),
                    callback_data=NavWhatsApp.GET_TRIAL,
                )
            )

    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def whatsapp_duration_keyboard(
    callback_data: WhatsAppData,
    prices: dict[int, int],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    duration_labels = {
        30: _("whatsapp:duration:30"),
        90: _("whatsapp:duration:90"),
        180: _("whatsapp:duration:180"),
        365: _("whatsapp:duration:365"),
    }

    for duration_days, price_rub in prices.items():
        callback_data.state = NavWhatsApp.DURATION
        callback_data.duration = duration_days
        callback_data.price = price_rub
        label = duration_labels.get(duration_days, f"{duration_days} days")
        builder.row(
            InlineKeyboardButton(
                text=f"{label} | {price_rub} \u20bd",
                callback_data=callback_data.pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=_("misc:button:back"),
            callback_data=NavWhatsApp.MAIN,
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def whatsapp_payment_method_keyboard(
    callback_data: WhatsAppData,
    stars_price: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    callback_data.state = NavWhatsApp.PAY_TELEGRAM_STARS
    callback_data.price = stars_price
    builder.row(
        InlineKeyboardButton(
            text=f"\u2b50 Telegram Stars | {stars_price} \u2605",
            callback_data=callback_data.pack(),
        )
    )

    callback_data.state = NavWhatsApp.BUY
    builder.row(
        InlineKeyboardButton(
            text=_("misc:button:back"),
            callback_data=callback_data.pack(),
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def whatsapp_success_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("whatsapp:button:show_info"),
            callback_data=NavWhatsApp.SHOW_INFO,
        )
    )
    builder.row(close_notification_button())
    return builder.as_markup()


def whatsapp_info_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("misc:button:back"),
            callback_data=NavWhatsApp.MAIN,
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()
