import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.is_dev import IsDev
from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.payment_gateways import GatewayFactory
from app.bot.utils.constants import TransactionStatus
from app.bot.utils.formatting import format_subscription_period
from app.bot.utils.navigation import NavSubscription
from app.db.models import Transaction, User

from .keyboard import pay_keyboard

logger = logging.getLogger(__name__)
router = Router(name=__name__)


class PaymentState(StatesGroup):
    processing = State()


@router.callback_query(SubscriptionData.filter(F.state.startswith(NavSubscription.PAY)))
async def callback_payment_method_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
    bot: Bot,
    gateway_factory: GatewayFactory,
    state: FSMContext,
) -> None:
    if await state.get_state() == PaymentState.processing:
        logger.debug(f"User {user.tg_id} is already processing payment.")
        return

    await state.set_state(PaymentState.processing)

    try:
        method = callback_data.state
        devices = callback_data.devices
        duration = callback_data.duration
        logger.info(f"User {user.tg_id} selected payment method: {method}")
        logger.info(f"User {user.tg_id} selected {devices} devices and {duration} days.")
        gateway = gateway_factory.get_gateway(method)
        plan = services.plan.get_plan(devices)
        price = plan.get_price(currency=gateway.currency, duration=duration)
        callback_data.price = price

        pay_url = await gateway.create_payment(callback_data)

        if callback_data.is_extend:
            text = _("payment:message:order_extend")
        elif callback_data.is_change:
            text = _("payment:message:order_change")
        else:
            text = _("payment:message:order")

        await callback.message.edit_text(
            text=text.format(
                devices=devices,
                duration=format_subscription_period(duration),
                price=price,
                currency=gateway.currency.symbol,
            ),
            reply_markup=pay_keyboard(pay_url=pay_url, callback_data=callback_data),
        )
    except Exception as exception:
        logger.error(f"Error processing payment: {exception}")
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
    finally:
        await state.set_state(None)


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, user: User) -> None:
    logger.info(f"Pre-checkout query received from user {user.tg_id}")
    if pre_checkout_query.invoice_payload:
        await pre_checkout_query.answer(ok=True)
    else:
        await pre_checkout_query.answer(ok=False)


@router.message(F.successful_payment)
async def successful_payment(
    message: Message,
    user: User,
    session: AsyncSession,
    bot: Bot,
    gateway_factory: GatewayFactory,
    services: ServicesContainer,
) -> None:
    if await IsDev()(user_id=user.tg_id):
        await bot.refund_star_payment(
            user_id=user.tg_id,
            telegram_payment_charge_id=message.successful_payment.telegram_payment_charge_id,
        )

    payload = message.successful_payment.invoice_payload

    # MTProto payment — payload format: "mtproto:{user_tg_id}:{duration}:{is_extend}"
    if payload.startswith("mtproto:"):
        parts = payload.split(":")
        user_tg_id = int(parts[1])
        duration_days = int(parts[2])
        is_extend = parts[3] == "True"

        transaction = await Transaction.create(
            session=session,
            tg_id=user.tg_id,
            subscription=payload,
            payment_id=message.successful_payment.telegram_payment_charge_id,
            status=TransactionStatus.COMPLETED,
        )

        if is_extend:
            await services.mtproto.extend(user_tg_id, duration_days)
        else:
            await services.mtproto.activate(user_tg_id, duration_days)

        link = await services.mtproto.get_link(user_tg_id)
        period = format_subscription_period(duration_days)

        from app.bot.routers.mtproto.keyboard import mtproto_success_keyboard

        if is_extend:
            await services.notification.notify_by_id(
                chat_id=user.tg_id,
                text=_("mtproto:message:extend_success").format(duration=period),
            )
        else:
            await services.notification.notify_by_id(
                chat_id=user.tg_id,
                text=_("mtproto:message:purchase_success").format(link=link),
                reply_markup=mtproto_success_keyboard(),
            )

        logger.info(f"MTProto payment succeeded for user {user.tg_id}, duration {duration_days}d")
        return

    # WhatsApp payment — payload format: "whatsapp:{user_tg_id}:{duration}:{is_extend}"
    if payload.startswith("whatsapp:"):
        parts = payload.split(":")
        user_tg_id = int(parts[1])
        duration_days = int(parts[2])
        is_extend = parts[3] == "True"

        transaction = await Transaction.create(
            session=session,
            tg_id=user.tg_id,
            subscription=payload,
            payment_id=message.successful_payment.telegram_payment_charge_id,
            status=TransactionStatus.COMPLETED,
        )

        if is_extend:
            await services.whatsapp.extend(user_tg_id, duration_days)
        else:
            await services.whatsapp.activate(user_tg_id, duration_days)

        info = await services.whatsapp.get_connection_info(user_tg_id)
        period = format_subscription_period(duration_days)

        from app.bot.routers.whatsapp.keyboard import whatsapp_success_keyboard

        if is_extend:
            await services.notification.notify_by_id(
                chat_id=user.tg_id,
                text=_("whatsapp:message:extend_success").format(duration=period),
            )
        else:
            host, port = info if info else ("", 0)
            await services.notification.notify_by_id(
                chat_id=user.tg_id,
                text=_("whatsapp:message:purchase_success").format(host=host, port=port),
                reply_markup=whatsapp_success_keyboard(),
            )

        logger.info(f"WhatsApp payment succeeded for user {user.tg_id}, duration {duration_days}d")
        return

    # VPN payment — standard SubscriptionData flow
    data = SubscriptionData.unpack(payload)
    transaction = await Transaction.create(
        session=session,
        tg_id=user.tg_id,
        subscription=data.pack(),
        payment_id=message.successful_payment.telegram_payment_charge_id,
        status=TransactionStatus.COMPLETED,
    )

    gateway = gateway_factory.get_gateway(NavSubscription.PAY_TELEGRAM_STARS)
    await gateway.handle_payment_succeeded(payment_id=transaction.payment_id)
