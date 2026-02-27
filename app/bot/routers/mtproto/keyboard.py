from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.models.mtproto_data import MTProtoData
from app.bot.routers.misc.keyboard import back_to_main_menu_button, close_notification_button
from app.bot.utils.navigation import NavMTProto


def mtproto_main_keyboard(
    has_subscription: bool,
    callback_data: MTProtoData,
    is_trial_available: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if has_subscription:
        builder.row(
            InlineKeyboardButton(
                text=_("mtproto:button:show_link"),
                callback_data=NavMTProto.SHOW_LINK,
            )
        )
        callback_data.state = NavMTProto.EXTEND
        callback_data.is_extend = True
        builder.row(
            InlineKeyboardButton(
                text=_("mtproto:button:extend"),
                callback_data=callback_data.pack(),
            )
        )
    else:
        callback_data.state = NavMTProto.BUY
        builder.row(
            InlineKeyboardButton(
                text=_("mtproto:button:buy"),
                callback_data=callback_data.pack(),
            )
        )
        if is_trial_available:
            builder.row(
                InlineKeyboardButton(
                    text=_("mtproto:button:trial"),
                    callback_data=NavMTProto.GET_TRIAL,
                )
            )

    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def mtproto_duration_keyboard(
    callback_data: MTProtoData,
    prices: dict[int, int],
    catalog=None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    duration_labels = {
        30: _("mtproto:duration:30"),
        90: _("mtproto:duration:90"),
        180: _("mtproto:duration:180"),
        365: _("mtproto:duration:365"),
    }

    for duration_days, price_rub in prices.items():
        callback_data.state = NavMTProto.DURATION
        callback_data.duration = duration_days
        callback_data.price = price_rub
        label = duration_labels.get(duration_days, f"{duration_days} days")

        discount_badge = ""
        if catalog:
            discount = catalog.get_discount_percent(duration_days)
            if discount > 0:
                discount_badge = f"  -{discount}%"

        builder.row(
            InlineKeyboardButton(
                text=f"{label} | {price_rub} \u20bd{discount_badge}",
                callback_data=callback_data.pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=_("misc:button:back"),
            callback_data=NavMTProto.MAIN,
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def mtproto_payment_method_keyboard(
    callback_data: MTProtoData,
    stars_price: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    callback_data.state = NavMTProto.PAY_TELEGRAM_STARS
    callback_data.price = stars_price
    builder.row(
        InlineKeyboardButton(
            text=f"\u2b50 Telegram Stars | {stars_price} \u2605",
            callback_data=callback_data.pack(),
        )
    )

    callback_data.state = NavMTProto.BUY
    builder.row(
        InlineKeyboardButton(
            text=_("misc:button:back"),
            callback_data=callback_data.pack(),
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def mtproto_success_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("mtproto:button:show_link"),
            callback_data=NavMTProto.SHOW_LINK,
        )
    )
    builder.row(close_notification_button())
    return builder.as_markup()


def mtproto_link_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(back_to_main_menu_button())
    return builder.as_markup()
