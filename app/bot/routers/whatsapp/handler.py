import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, LabeledPrice
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.filters.is_dev import IsDev
from app.bot.models import ServicesContainer
from app.bot.models.whatsapp_data import WhatsAppData
from app.bot.utils.formatting import format_subscription_period
from app.bot.utils.navigation import NavWhatsApp
from app.config import Config
from app.db.models import User

from .keyboard import (
    whatsapp_duration_keyboard,
    whatsapp_info_keyboard,
    whatsapp_main_keyboard,
    whatsapp_payment_method_keyboard,
    whatsapp_success_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name=__name__)


@router.callback_query(F.data == NavWhatsApp.MAIN)
async def callback_whatsapp_main(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} opened WhatsApp Proxy page.")

    sub = await services.whatsapp.get_subscription(user.tg_id)
    has_subscription = sub is not None and sub.is_active and await services.whatsapp.is_active(user.tg_id)

    if has_subscription:
        text = _("whatsapp:message:active").format(
            expires_at=sub.expires_at.strftime("%d.%m.%Y %H:%M UTC"),
        )
    else:
        text = _("whatsapp:message:not_active")

    callback_data = WhatsAppData(state=NavWhatsApp.BUY, user_id=user.tg_id)
    is_trial_available = await services.whatsapp.is_trial_available(user.tg_id)

    await callback.message.edit_text(
        text=text,
        reply_markup=whatsapp_main_keyboard(
            has_subscription=has_subscription,
            callback_data=callback_data,
            is_trial_available=is_trial_available and config.shop.WHATSAPP_TRIAL_PERIOD > 0,
        ),
    )


@router.callback_query(WhatsAppData.filter(F.state == NavWhatsApp.BUY))
async def callback_whatsapp_buy(
    callback: CallbackQuery,
    user: User,
    callback_data: WhatsAppData,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} started WhatsApp Proxy purchase.")

    prices = {
        30: config.shop.WHATSAPP_PRICE_30,
        90: config.shop.WHATSAPP_PRICE_90,
        180: config.shop.WHATSAPP_PRICE_180,
        365: config.shop.WHATSAPP_PRICE_365,
    }

    callback_data.user_id = user.tg_id
    await callback.message.edit_text(
        text=_("whatsapp:message:choose_duration"),
        reply_markup=whatsapp_duration_keyboard(
            callback_data=callback_data,
            prices=prices,
        ),
    )


@router.callback_query(WhatsAppData.filter(F.state == NavWhatsApp.EXTEND))
async def callback_whatsapp_extend(
    callback: CallbackQuery,
    user: User,
    callback_data: WhatsAppData,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} started WhatsApp Proxy extend.")

    prices = {
        30: config.shop.WHATSAPP_PRICE_30,
        90: config.shop.WHATSAPP_PRICE_90,
        180: config.shop.WHATSAPP_PRICE_180,
        365: config.shop.WHATSAPP_PRICE_365,
    }

    callback_data.user_id = user.tg_id
    callback_data.is_extend = True
    await callback.message.edit_text(
        text=_("whatsapp:message:choose_duration"),
        reply_markup=whatsapp_duration_keyboard(
            callback_data=callback_data,
            prices=prices,
        ),
    )


@router.callback_query(WhatsAppData.filter(F.state == NavWhatsApp.DURATION))
async def callback_whatsapp_duration_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: WhatsAppData,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} selected WhatsApp duration: {callback_data.duration} days")

    stars_price = services.whatsapp.get_price_stars(callback_data.duration)
    if stars_price is None:
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
        return

    callback_data.user_id = user.tg_id
    rub_price = services.whatsapp.get_price(callback_data.duration)
    period = format_subscription_period(callback_data.duration)

    text = _("whatsapp:message:confirm_order").format(
        duration=period,
        price_rub=rub_price,
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=whatsapp_payment_method_keyboard(
            callback_data=callback_data,
            stars_price=stars_price,
        ),
    )


@router.callback_query(WhatsAppData.filter(F.state == NavWhatsApp.PAY_TELEGRAM_STARS))
async def callback_whatsapp_pay_stars(
    callback: CallbackQuery,
    user: User,
    callback_data: WhatsAppData,
    services: ServicesContainer,
    bot: Bot,
) -> None:
    logger.info(f"User {user.tg_id} paying for WhatsApp Proxy via Stars: {callback_data.price} stars")

    if await IsDev()(user_id=user.tg_id):
        amount = 1
    else:
        amount = int(callback_data.price)

    period = format_subscription_period(callback_data.duration)
    title = _("whatsapp:invoice:title").format(duration=period)
    description = _("whatsapp:invoice:description").format(duration=period)

    # Encode payment data in payload
    payload = f"whatsapp:{user.tg_id}:{callback_data.duration}:{callback_data.is_extend}"

    try:
        pay_url = await bot.create_invoice_link(
            title=title,
            description=description,
            prices=[LabeledPrice(label="XTR", amount=amount)],
            payload=payload,
            currency="XTR",
        )

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text=_("subscription:button:pay"), url=pay_url))
        builder.row(
            InlineKeyboardButton(text=_("misc:button:back"), callback_data=NavWhatsApp.MAIN)
        )

        await callback.message.edit_text(
            text=_("whatsapp:message:pay").format(amount=amount),
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        logger.error(f"Failed to create WhatsApp payment: {e}")
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))


@router.callback_query(F.data == NavWhatsApp.GET_TRIAL)
async def callback_whatsapp_trial(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} requesting WhatsApp Proxy trial.")

    if not await services.whatsapp.is_trial_available(user.tg_id):
        await services.notification.show_popup(
            callback=callback,
            text=_("whatsapp:popup:trial_unavailable"),
        )
        return

    trial_days = config.shop.WHATSAPP_TRIAL_PERIOD
    port = await services.whatsapp.activate(user.tg_id, trial_days, is_trial=True)

    if not port:
        await services.notification.show_popup(
            callback=callback,
            text=_("whatsapp:popup:trial_failed"),
        )
        return

    period = format_subscription_period(trial_days)

    await callback.message.edit_text(
        text=_("whatsapp:message:trial_success").format(
            duration=period,
            host=services.whatsapp.host,
            port=port,
        ),
        reply_markup=whatsapp_success_keyboard(),
    )


@router.callback_query(F.data == NavWhatsApp.SHOW_INFO)
async def callback_whatsapp_show_info(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} requesting WhatsApp connection info.")

    info = await services.whatsapp.get_connection_info(user.tg_id)
    if not info:
        await services.notification.show_popup(
            callback=callback,
            text=_("whatsapp:popup:no_subscription"),
        )
        return

    host, port = info

    await callback.message.edit_text(
        text=_("whatsapp:message:connection_info").format(
            host=host,
            port=port,
        ),
        reply_markup=whatsapp_info_keyboard(),
    )
