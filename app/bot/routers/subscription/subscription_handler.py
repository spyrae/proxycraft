import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.models import ClientData, ServicesContainer, SubscriptionData
from app.bot.payment_gateways import GatewayFactory
from app.bot.utils.navigation import NavSubscription
from app.config import Config
from app.db.models import User

from .keyboard import (
    change_operator_keyboard,
    devices_keyboard,
    duration_keyboard,
    operator_keyboard,
    payment_method_keyboard,
    subscription_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name=__name__)


async def show_subscription(
    callback: CallbackQuery,
    client_data: ClientData | None,
    callback_data: SubscriptionData,
    has_operators: bool = False,
) -> None:
    if client_data:

        if client_data.has_subscription_expired:
            text = _("subscription:message:expired")
        else:
            text = _("subscription:message:active").format(
                devices=client_data.max_devices,
                expiry_time=client_data.expiry_time,
            )
    else:
        text = _("subscription:message:not_active")

    await callback.message.edit_text(
        text=text,
        reply_markup=subscription_keyboard(
            has_subscription=client_data,
            callback_data=callback_data,
            has_operators=has_operators,
        ),
    )


@router.callback_query(F.data == NavSubscription.MAIN)
async def callback_subscription(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} opened subscription page.")
    await state.set_state(None)

    client_data = None
    if user.server_id:
        client_data = await services.vpn.get_client_data(user)
        if not client_data:
            await services.notification.show_popup(
                callback=callback,
                text=_("subscription:popup:error_fetching_data"),
            )
            return

    callback_data = SubscriptionData(state=NavSubscription.PROCESS, user_id=user.tg_id)
    has_operators = bool(services.product_catalog.get_operators())
    await show_subscription(
        callback=callback,
        client_data=client_data,
        callback_data=callback_data,
        has_operators=has_operators,
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.EXTEND))
async def callback_subscription_extend(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    config: Config,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} started extend subscription.")
    client = await services.vpn.is_client_exists(user)

    current_devices = await services.vpn.get_limit_ip(user=user, client=client)
    if not services.product_catalog.get_vpn_product_by_devices(current_devices):
        await services.notification.show_popup(
            callback=callback,
            text=_("subscription:popup:error_fetching_plan"),
        )
        return

    callback_data.devices = current_devices
    callback_data.state = NavSubscription.DURATION
    callback_data.is_extend = True
    await callback.message.edit_text(
        text=_("subscription:message:duration"),
        reply_markup=duration_keyboard(
            catalog=services.product_catalog,
            callback_data=callback_data,
            currency=config.shop.CURRENCY,
        ),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.CHANGE))
async def callback_subscription_change(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} started change subscription.")
    callback_data.state = NavSubscription.DEVICES
    callback_data.is_change = True
    await callback.message.edit_text(
        text=_("subscription:message:devices"),
        reply_markup=devices_keyboard(services.product_catalog.get_vpn_products(), callback_data),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.PROCESS))
async def callback_subscription_process(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    callback_data: SubscriptionData,
    state: FSMContext,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} started subscription process.")
    server = await services.server_pool.get_available_server()

    if not server:
        await services.notification.show_popup(
            callback=callback,
            text=_("subscription:popup:no_available_servers"),
            cache_time=120,
        )
        return

    # Save callback_data in FSM for use after operator selection
    await state.update_data(sub_callback=callback_data.pack())

    # Show operator selection
    operators = services.product_catalog.get_operators()
    if operators:
        await callback.message.edit_text(
            text=_("subscription:message:operator"),
            reply_markup=operator_keyboard(operators),
        )
    else:
        # No operators configured — skip to devices
        callback_data.state = NavSubscription.DEVICES
        await callback.message.edit_text(
            text=_("subscription:message:devices"),
            reply_markup=devices_keyboard(services.product_catalog.get_vpn_products(), callback_data),
        )


@router.callback_query(F.data.startswith("set_operator:"))
async def callback_operator_selected(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    state: FSMContext,
    services: ServicesContainer,
) -> None:
    operator_slug = callback.data.split(":")[1]
    logger.info(f"User {user.tg_id} selected operator: {operator_slug}")

    # Save operator to User
    await User.update(session=session, tg_id=user.tg_id, operator=operator_slug)

    # Restore callback_data from FSM
    fsm_data = await state.get_data()
    callback_data = SubscriptionData.unpack(fsm_data["sub_callback"])
    callback_data.state = NavSubscription.DEVICES

    await callback.message.edit_text(
        text=_("subscription:message:devices"),
        reply_markup=devices_keyboard(services.product_catalog.get_vpn_products(), callback_data),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.DEVICES))
async def callback_devices_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    config: Config,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} selected devices: {callback_data.devices}")
    callback_data.state = NavSubscription.DURATION
    await callback.message.edit_text(
        text=_("subscription:message:duration"),
        reply_markup=duration_keyboard(
            catalog=services.product_catalog,
            callback_data=callback_data,
            currency=config.shop.CURRENCY,
        ),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.DURATION))
async def callback_duration_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
    gateway_factory: GatewayFactory,
) -> None:
    logger.info(f"User {user.tg_id} selected duration: {callback_data.duration}")
    product = services.product_catalog.get_vpn_product_by_devices(callback_data.devices)
    callback_data.state = NavSubscription.PAY
    await callback.message.edit_text(
        text=_("subscription:message:payment_method"),
        reply_markup=payment_method_keyboard(
            product=product,
            callback_data=callback_data,
            gateways=gateway_factory.get_gateways(),
        ),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.CHANGE_OPERATOR))
async def callback_change_operator(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} wants to change operator.")
    await callback.message.edit_text(
        text=_("subscription:message:operator"),
        reply_markup=change_operator_keyboard(services.product_catalog.get_operators()),
    )


@router.callback_query(F.data.startswith("change_op:"))
async def callback_change_operator_selected(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    services: ServicesContainer,
) -> None:
    new_operator = callback.data.split(":")[1]
    logger.info(f"User {user.tg_id} changing operator to: {new_operator}")

    success = await services.vpn.change_operator(user, new_operator)
    if success:
        await User.update(session=session, tg_id=user.tg_id, operator=new_operator)
        await services.notification.show_popup(
            callback=callback,
            text=_("subscription:popup:operator_changed"),
        )
    else:
        await services.notification.show_popup(
            callback=callback,
            text=_("subscription:popup:operator_change_failed"),
        )

    # Return to subscription page
    client_data = await services.vpn.get_client_data(user)
    callback_data = SubscriptionData(state=NavSubscription.PROCESS, user_id=user.tg_id)
    has_operators = bool(services.product_catalog.get_operators())
    await show_subscription(
        callback=callback,
        client_data=client_data,
        callback_data=callback_data,
        has_operators=has_operators,
    )
