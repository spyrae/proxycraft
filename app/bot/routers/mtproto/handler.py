import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, LabeledPrice
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.filters.is_dev import IsDev
from app.bot.models import ServicesContainer
from app.bot.models.mtproto_data import MTProtoData
from app.bot.utils.formatting import format_subscription_period
from app.bot.utils.navigation import NavMTProto
from app.config import Config
from app.db.models import User

from .keyboard import (
    mtproto_duration_keyboard,
    mtproto_main_keyboard,
    mtproto_payment_method_keyboard,
    mtproto_success_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name=__name__)


@router.callback_query(F.data == NavMTProto.MAIN)
async def callback_mtproto_main(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} opened MTProto page.")

    sub = await services.mtproto.get_subscription(user.tg_id)
    logger.debug(f"MTProto sub for {user.tg_id}: {sub}, is_active={sub.is_active if sub else None}")
    has_subscription = sub is not None and sub.is_active and await services.mtproto.is_active(user.tg_id)
    logger.debug(f"MTProto has_subscription={has_subscription}")

    if has_subscription:
        text = _("mtproto:message:active").format(
            expires_at=sub.expires_at.strftime("%d.%m.%Y %H:%M UTC"),
        )
    else:
        text = _("mtproto:message:not_active")

    callback_data = MTProtoData(state=NavMTProto.BUY, user_id=user.tg_id)
    is_trial_available = await services.mtproto.is_trial_available(user.tg_id)

    await callback.message.edit_text(
        text=text,
        reply_markup=mtproto_main_keyboard(
            has_subscription=has_subscription,
            callback_data=callback_data,
            is_trial_available=is_trial_available and config.shop.MTPROTO_TRIAL_PERIOD > 0,
        ),
    )


@router.callback_query(MTProtoData.filter(F.state == NavMTProto.BUY))
async def callback_mtproto_buy(
    callback: CallbackQuery,
    user: User,
    callback_data: MTProtoData,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} started MTProto purchase.")

    prices = {
        30: config.shop.MTPROTO_PRICE_30,
        90: config.shop.MTPROTO_PRICE_90,
        180: config.shop.MTPROTO_PRICE_180,
        365: config.shop.MTPROTO_PRICE_365,
    }

    callback_data.user_id = user.tg_id
    await callback.message.edit_text(
        text=_("mtproto:message:choose_duration"),
        reply_markup=mtproto_duration_keyboard(
            callback_data=callback_data,
            prices=prices,
        ),
    )


@router.callback_query(MTProtoData.filter(F.state == NavMTProto.EXTEND))
async def callback_mtproto_extend(
    callback: CallbackQuery,
    user: User,
    callback_data: MTProtoData,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} started MTProto extend.")

    prices = {
        30: config.shop.MTPROTO_PRICE_30,
        90: config.shop.MTPROTO_PRICE_90,
        180: config.shop.MTPROTO_PRICE_180,
        365: config.shop.MTPROTO_PRICE_365,
    }

    callback_data.user_id = user.tg_id
    callback_data.is_extend = True
    await callback.message.edit_text(
        text=_("mtproto:message:choose_duration"),
        reply_markup=mtproto_duration_keyboard(
            callback_data=callback_data,
            prices=prices,
        ),
    )


@router.callback_query(MTProtoData.filter(F.state == NavMTProto.DURATION))
async def callback_mtproto_duration_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: MTProtoData,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} selected MTProto duration: {callback_data.duration} days")

    stars_price = services.mtproto.get_price_stars(callback_data.duration)
    if stars_price is None:
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
        return

    callback_data.user_id = user.tg_id
    rub_price = services.mtproto.get_price(callback_data.duration)
    period = format_subscription_period(callback_data.duration)

    text = _("mtproto:message:confirm_order").format(
        duration=period,
        price_rub=rub_price,
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=mtproto_payment_method_keyboard(
            callback_data=callback_data,
            stars_price=stars_price,
        ),
    )


@router.callback_query(MTProtoData.filter(F.state == NavMTProto.PAY_TELEGRAM_STARS))
async def callback_mtproto_pay_stars(
    callback: CallbackQuery,
    user: User,
    callback_data: MTProtoData,
    services: ServicesContainer,
    bot: Bot,
) -> None:
    logger.info(f"User {user.tg_id} paying for MTProto via Stars: {callback_data.price} stars")

    if await IsDev()(user_id=user.tg_id):
        amount = 1
    else:
        amount = int(callback_data.price)

    period = format_subscription_period(callback_data.duration)
    title = _("mtproto:invoice:title").format(duration=period)
    description = _("mtproto:invoice:description").format(duration=period)

    # Encode payment data in payload
    payload = f"mtproto:{user.tg_id}:{callback_data.duration}:{callback_data.is_extend}"

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
            InlineKeyboardButton(text=_("misc:button:back"), callback_data=NavMTProto.MAIN)
        )

        await callback.message.edit_text(
            text=_("mtproto:message:pay").format(amount=amount),
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        logger.error(f"Failed to create MTProto payment: {e}")
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))


@router.callback_query(F.data == NavMTProto.GET_TRIAL)
async def callback_mtproto_trial(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} requesting MTProto trial.")

    if not await services.mtproto.is_trial_available(user.tg_id):
        await services.notification.show_popup(
            callback=callback,
            text=_("mtproto:popup:trial_unavailable"),
        )
        return

    trial_days = config.shop.MTPROTO_TRIAL_PERIOD
    secret = await services.mtproto.activate(user.tg_id, trial_days, is_trial=True)

    if not secret:
        await services.notification.show_popup(
            callback=callback,
            text=_("mtproto:popup:trial_failed"),
        )
        return

    link = await services.mtproto.get_link(user.tg_id)
    period = format_subscription_period(trial_days)

    await callback.message.edit_text(
        text=_("mtproto:message:trial_success").format(duration=period, link=link),
        reply_markup=mtproto_success_keyboard(),
    )


@router.callback_query(F.data == NavMTProto.SHOW_LINK)
async def callback_mtproto_show_link(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} requesting MTProto link.")

    link = await services.mtproto.get_link(user.tg_id)
    logger.debug(f"MTProto link for {user.tg_id}: {link}")
    if not link:
        await services.notification.show_popup(
            callback=callback,
            text=_("mtproto:popup:no_subscription"),
        )
        return

    text = _("mtproto:message:link").format(link=link)
    logger.debug(f"MTProto link text: {text!r}")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("mtproto:button:connect_proxy"),
            url=link,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("misc:button:back"),
            callback_data=NavMTProto.MAIN,
        )
    )

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=builder.as_markup(),
        )
        logger.debug(f"MTProto link message sent to {user.tg_id}")
    except Exception as e:
        logger.error(f"MTProto link edit_text failed for {user.tg_id}: {e}")
