from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.models.bundle_data import BundleData
from app.bot.routers.misc.keyboard import back_to_main_menu_button
from app.bot.services.product_catalog import ProductCatalog
from app.bot.utils.navigation import NavBundle


def bundle_select_keyboard(
    catalog: ProductCatalog,
    user_id: int,
) -> InlineKeyboardMarkup:
    """Keyboard with available bundles and their base prices."""
    builder = InlineKeyboardBuilder()

    for bundle in catalog.get_bundles():
        price_rub = catalog.calculate_price_rub(bundle.slug, 30)
        callback_data = BundleData(
            state=NavBundle.SELECT,
            slug=bundle.slug,
            user_id=user_id,
        )
        builder.row(
            InlineKeyboardButton(
                text=f"{bundle.emoji} {bundle.name} | от {price_rub} ₽/мес",
                callback_data=callback_data.pack(),
            )
        )

    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def bundle_duration_keyboard(
    catalog: ProductCatalog,
    callback_data: BundleData,
) -> InlineKeyboardMarkup:
    """Keyboard with duration options and discount badges."""
    builder = InlineKeyboardBuilder()

    duration_labels = {
        30: _("mtproto:duration:30"),
        90: _("mtproto:duration:90"),
        180: _("mtproto:duration:180"),
        365: _("mtproto:duration:365"),
    }

    for duration in catalog.get_durations():
        price_rub = catalog.calculate_price_rub(callback_data.slug, duration)
        discount = catalog.get_discount_percent(duration)

        label = duration_labels.get(duration, f"{duration} days")
        badge = f"  -{discount}%" if discount > 0 else ""

        cb = BundleData(
            state=NavBundle.DURATION,
            slug=callback_data.slug,
            user_id=callback_data.user_id,
            duration=duration,
            price=price_rub,
            is_extend=callback_data.is_extend,
        )
        builder.row(
            InlineKeyboardButton(
                text=f"{label} | {price_rub} ₽{badge}",
                callback_data=cb.pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=_("misc:button:back"),
            callback_data=NavBundle.MAIN,
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def bundle_payment_keyboard(
    callback_data: BundleData,
    stars_price: int,
) -> InlineKeyboardMarkup:
    """Payment keyboard for bundle (Stars only)."""
    builder = InlineKeyboardBuilder()

    cb = BundleData(
        state=NavBundle.PAY_TELEGRAM_STARS,
        slug=callback_data.slug,
        user_id=callback_data.user_id,
        duration=callback_data.duration,
        price=stars_price,
        is_extend=callback_data.is_extend,
    )
    builder.row(
        InlineKeyboardButton(
            text=f"⭐ Telegram Stars | {stars_price} ★",
            callback_data=cb.pack(),
        )
    )

    builder.row(
        InlineKeyboardButton(
            text=_("misc:button:back"),
            callback_data=NavBundle.MAIN,
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def bundle_success_keyboard() -> InlineKeyboardMarkup:
    """Post-purchase/trial success keyboard."""
    from app.bot.routers.misc.keyboard import close_notification_button

    builder = InlineKeyboardBuilder()
    builder.row(close_notification_button())
    return builder.as_markup()
