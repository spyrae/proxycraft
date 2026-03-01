from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bot.services.product_catalog import Operator, Product, ProductCatalog

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.models import SubscriptionData
from app.bot.payment_gateways import PaymentGateway
from app.bot.routers.misc.keyboard import (
    back_button,
    back_to_main_menu_button,
    close_notification_button,
)
from app.bot.utils.constants import Currency
from app.bot.utils.formatting import format_device_count, format_subscription_period
from app.bot.utils.navigation import NavDownload, NavMain, NavSubscription


def change_subscription_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=_("subscription:button:change"),
        callback_data=NavSubscription.CHANGE,
    )


def subscription_keyboard(
    has_subscription: bool,
    callback_data: SubscriptionData,
    has_operators: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if not has_subscription:
        builder.button(
            text=_("subscription:button:buy"),
            callback_data=callback_data,
        )
    else:
        callback_data.state = NavSubscription.EXTEND
        builder.button(
            text=_("subscription:button:extend"),
            callback_data=callback_data,
        )
        callback_data.state = NavSubscription.CHANGE
        builder.button(
            text=_("subscription:button:change"),
            callback_data=callback_data,
        )
        if has_operators:
            callback_data.state = NavSubscription.CHANGE_OPERATOR
            builder.button(
                text=_("subscription:button:change_operator"),
                callback_data=callback_data,
            )

    builder.button(
        text=_("subscription:button:activate_promocode"),
        callback_data=NavSubscription.PROMOCODE,
    )
    builder.adjust(1)
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def devices_keyboard(
    products: list[Product],
    callback_data: SubscriptionData,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for product in products:
        callback_data.devices = product.devices
        builder.button(
            text=format_device_count(product.devices),
            callback_data=callback_data,
        )

    builder.adjust(2)
    builder.row(back_button(NavSubscription.MAIN))
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def duration_keyboard(
    catalog: ProductCatalog,
    callback_data: SubscriptionData,
    currency: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    durations = catalog.get_durations()
    currency_obj: Currency = Currency.from_code(currency)
    product = catalog.get_vpn_product_by_devices(callback_data.devices)

    for duration in durations:
        callback_data.duration = duration
        period = format_subscription_period(duration)
        price = catalog.get_price(product.slug, currency_obj.code, duration)
        builder.button(
            text=f"{period} | {price} {currency_obj.symbol}",
            callback_data=callback_data,
        )

    builder.adjust(2)

    if callback_data.is_extend:
        builder.row(back_button(NavSubscription.MAIN))
    else:
        callback_data.state = NavSubscription.PROCESS
        builder.row(
            back_button(
                callback_data.pack(),
                text=_("subscription:button:change_devices"),
            )
        )

    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def pay_keyboard(pay_url: str, callback_data: SubscriptionData) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text=_("subscription:button:pay"), url=pay_url))

    callback_data.state = NavSubscription.DURATION
    builder.row(
        back_button(
            callback_data.pack(),
            text=_("subscription:button:change_payment_method"),
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def payment_method_keyboard(
    product: Product,
    callback_data: SubscriptionData,
    gateways: list[PaymentGateway],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for gateway in gateways:
        price = product.prices.get(gateway.currency.code, {}).get(callback_data.duration) if product.prices else None
        if price is None:
            continue

        callback_data.state = gateway.callback
        builder.row(
            InlineKeyboardButton(
                text=f"{gateway.name} | {price} {gateway.currency.symbol}",
                callback_data=callback_data.pack(),
            )
        )

    callback_data.state = NavSubscription.DEVICES
    builder.row(
        back_button(
            callback_data.pack(),
            text=_("subscription:button:change_duration"),
        )
    )

    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def payment_success_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=_("subscription:button:download_app"),
            callback_data=NavMain.REDIRECT_TO_DOWNLOAD,
        )
    )

    builder.row(close_notification_button())
    return builder.as_markup()


def trial_success_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=_("subscription:button:connect"),
            callback_data=NavDownload.MAIN,
        )
    )

    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def operator_keyboard(operators: list[Operator]) -> InlineKeyboardMarkup:
    """Keyboard for selecting mobile operator during subscription purchase."""
    builder = InlineKeyboardBuilder()
    for op in operators:
        builder.button(
            text=f"{op.emoji} {op.name}",
            callback_data=f"set_operator:{op.slug}",
        )
    builder.adjust(1)
    builder.row(back_button(NavSubscription.MAIN))
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def trial_operator_keyboard(operators: list[Operator]) -> InlineKeyboardMarkup:
    """Keyboard for selecting mobile operator during trial activation."""
    builder = InlineKeyboardBuilder()
    for op in operators:
        builder.button(
            text=f"{op.emoji} {op.name}",
            callback_data=f"trial_operator:{op.slug}",
        )
    builder.adjust(1)
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def change_operator_keyboard(operators: list[Operator]) -> InlineKeyboardMarkup:
    """Keyboard for changing operator for existing subscribers."""
    builder = InlineKeyboardBuilder()
    for op in operators:
        builder.button(
            text=f"{op.emoji} {op.name}",
            callback_data=f"change_op:{op.slug}",
        )
    builder.adjust(1)
    builder.row(back_button(NavSubscription.MAIN))
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def promocode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(back_button(NavSubscription.MAIN))
    builder.row(back_to_main_menu_button())
    return builder.as_markup()
