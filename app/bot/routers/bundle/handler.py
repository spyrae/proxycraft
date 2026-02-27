import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, LabeledPrice
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.is_dev import IsDev
from app.bot.models import ServicesContainer
from app.bot.models.bundle_data import BundleData
from app.bot.utils.formatting import format_subscription_period
from app.bot.utils.navigation import NavBundle
from app.config import Config
from app.db.models import User

from .keyboard import (
    bundle_duration_keyboard,
    bundle_payment_keyboard,
    bundle_select_keyboard,
    bundle_success_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name=__name__)


@router.callback_query(F.data == NavBundle.MAIN)
async def callback_bundle_main(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
) -> None:
    """Show bundle selection screen."""
    logger.info(f"User {user.tg_id} opened bundles page.")

    await callback.message.edit_text(
        text=_("bundle:message:select"),
        reply_markup=bundle_select_keyboard(
            catalog=services.product_catalog,
            user_id=user.tg_id,
        ),
    )


@router.callback_query(BundleData.filter(F.state == NavBundle.SELECT))
async def callback_bundle_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: BundleData,
    services: ServicesContainer,
) -> None:
    """Show duration selection for a bundle."""
    logger.info(f"User {user.tg_id} selected bundle: {callback_data.slug}")

    product = services.product_catalog.get_product(callback_data.slug)
    if not product:
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
        return

    await callback.message.edit_text(
        text=_("bundle:message:choose_duration").format(
            name=product.name,
            emoji=product.emoji,
            description=product.description,
        ),
        reply_markup=bundle_duration_keyboard(
            catalog=services.product_catalog,
            callback_data=callback_data,
        ),
    )


@router.callback_query(BundleData.filter(F.state == NavBundle.DURATION))
async def callback_bundle_duration_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: BundleData,
    services: ServicesContainer,
) -> None:
    """Show payment confirmation for a bundle."""
    logger.info(
        f"User {user.tg_id} selected bundle duration: "
        f"{callback_data.slug} / {callback_data.duration} days"
    )

    catalog = services.product_catalog
    stars_price = catalog.calculate_price_stars(callback_data.slug, callback_data.duration)
    rub_price = catalog.calculate_price_rub(callback_data.slug, callback_data.duration)
    period = format_subscription_period(callback_data.duration)
    discount = catalog.get_discount_percent(callback_data.duration)

    product = catalog.get_product(callback_data.slug)
    discount_text = f"\n💰 Скидка: {discount}%" if discount > 0 else ""

    text = _("bundle:message:confirm_order").format(
        name=product.name,
        duration=period,
        price_rub=rub_price,
        discount=discount_text,
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=bundle_payment_keyboard(
            callback_data=callback_data,
            stars_price=stars_price,
        ),
    )


@router.callback_query(BundleData.filter(F.state == NavBundle.PAY_TELEGRAM_STARS))
async def callback_bundle_pay_stars(
    callback: CallbackQuery,
    user: User,
    callback_data: BundleData,
    services: ServicesContainer,
    bot: Bot,
) -> None:
    """Create Stars invoice for bundle purchase."""
    logger.info(
        f"User {user.tg_id} paying for bundle {callback_data.slug} "
        f"via Stars: {callback_data.price} stars"
    )

    if await IsDev()(user_id=user.tg_id):
        amount = 1
    else:
        amount = int(callback_data.price)

    period = format_subscription_period(callback_data.duration)
    product = services.product_catalog.get_product(callback_data.slug)

    title = _("bundle:invoice:title").format(name=product.name, duration=period)
    description = _("bundle:invoice:description").format(
        name=product.name, duration=period
    )

    # Payload format: "bundle:{slug}:{duration}:{is_extend}"
    payload = f"bundle:{callback_data.slug}:{callback_data.duration}:{callback_data.is_extend}"

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
            InlineKeyboardButton(text=_("misc:button:back"), callback_data=NavBundle.MAIN)
        )

        await callback.message.edit_text(
            text=_("bundle:message:pay").format(amount=amount),
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        logger.error(f"Failed to create bundle payment: {e}")
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))


@router.callback_query(F.data == NavBundle.GET_TRIAL)
async def callback_bundle_trial(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
    config: Config,
    session: AsyncSession,
) -> None:
    """Activate trial for a bundle (activate all components for trial_days)."""
    logger.info(f"User {user.tg_id} requesting bundle trial.")

    # For now, use the first available bundle (Мессенджеры)
    # This can be extended to support a specific bundle slug via callback_data
    bundles = services.product_catalog.get_bundles()
    if not bundles:
        await services.notification.show_popup(
            callback=callback, text=_("bundle:popup:trial_unavailable")
        )
        return

    bundle = bundles[0]
    trial_days = bundle.trial_days

    # Check trial availability for all components
    for component in bundle.includes:
        if component == "mtproto":
            if not await services.mtproto.is_trial_available(user.tg_id):
                await services.notification.show_popup(
                    callback=callback, text=_("bundle:popup:trial_unavailable")
                )
                return
        elif component == "socks5":
            if not await services.whatsapp.is_trial_available(user.tg_id):
                await services.notification.show_popup(
                    callback=callback, text=_("bundle:popup:trial_unavailable")
                )
                return

    results = await services.bundle.activate(
        slug=bundle.slug,
        user_tg_id=user.tg_id,
        user=user,
        duration=trial_days,
        is_trial=True,
    )

    # Check if all succeeded
    all_success = all(r.get("success", False) for r in results.values())
    if not all_success:
        await services.notification.show_popup(
            callback=callback, text=_("bundle:popup:trial_failed")
        )
        return

    period = format_subscription_period(trial_days)
    await callback.message.edit_text(
        text=_("bundle:message:trial_success").format(
            name=bundle.name, duration=period
        ),
        reply_markup=bundle_success_keyboard(),
    )
