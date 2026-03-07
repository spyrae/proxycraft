import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.models import ServicesContainer
from app.bot.routers.subscription.keyboard import trial_operator_keyboard, trial_success_keyboard
from app.bot.utils.constants import MAIN_MESSAGE_ID_KEY, PREVIOUS_CALLBACK_KEY
from app.bot.utils.formatting import format_subscription_period
from app.bot.utils.navigation import NavMain, NavSubscription
from app.bot.utils.qr import generate_qr
from app.config import Config
from app.db.models import User

logger = logging.getLogger(__name__)
router = Router(name=__name__)


async def _activate_trial(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    services: ServicesContainer,
    config: Config,
) -> None:
    """Activate trial for user (operator must already be set)."""
    trial_period = config.shop.TRIAL_PERIOD
    success = await services.subscription.gift_trial(user=user)

    main_message_id = await state.get_value(MAIN_MESSAGE_ID_KEY)
    if success:
        await callback.bot.edit_message_text(
            text=_("subscription:ntf:trial_activate_success").format(
                duration=format_subscription_period(trial_period),
            ),
            chat_id=callback.message.chat.id,
            message_id=main_message_id,
            reply_markup=trial_success_keyboard(),
        )
        key = await services.vpn.get_key(user)
        if key:
            qr_photo = await generate_qr(key)
            await callback.bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=qr_photo,
                caption=_("qr:caption:scan"),
            )
    else:
        text = _("subscription:popup:trial_activate_failed")
        await services.notification.show_popup(callback=callback, text=text)


@router.callback_query(F.data == NavSubscription.GET_TRIAL)
async def callback_get_trial(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} triggered getting non-referral trial period.")
    await state.update_data({PREVIOUS_CALLBACK_KEY: NavMain.MAIN_MENU})

    server = await services.server_pool.get_available_server()

    if not server:
        await services.notification.show_popup(
            callback=callback, text=_("subscription:popup:no_available_servers")
        )
        return

    is_trial_available = await services.subscription.is_trial_available(user=user)

    if not is_trial_available:
        await services.notification.show_popup(
            callback=callback, text=_("subscription:popup:trial_unavailable_for_user")
        )
        return

    # If operator not yet selected, show operator selection first
    operators = services.product_catalog.get_operators()
    if not user.operator and operators:
        await callback.message.edit_text(
            text=_("subscription:message:operator"),
            reply_markup=trial_operator_keyboard(operators, lang=user.language_code),
        )
        return

    # Operator already set or no operators configured — activate directly
    await _activate_trial(callback, user, state, services, config)


@router.callback_query(F.data.startswith("trial_operator:"))
async def callback_trial_operator_selected(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    state: FSMContext,
    services: ServicesContainer,
    config: Config,
) -> None:
    operator_slug = callback.data.split(":")[1]
    logger.info(f"User {user.tg_id} selected trial operator: {operator_slug}")

    # Save operator to User
    await User.update(session=session, tg_id=user.tg_id, operator=operator_slug)
    user.operator = operator_slug  # update in-memory

    await _activate_trial(callback, user, state, services, config)
