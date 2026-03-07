import asyncio
import logging
import uuid
from datetime import datetime, timezone

from aiohttp import web
from aiohttp.web import Application, Request, Response

from aiogram.types import LabeledPrice

from sqlalchemy import func, select, or_
from sqlalchemy.orm import selectinload

from app.bot.api.middleware import (
    require_admin,
    _validate_telegram_login,
    _create_admin_token,
)
from app.bot.api.serializers import (
    serialize_admin_server,
    serialize_admin_user,
    serialize_admin_user_detail,
    serialize_bundle_plans,
    serialize_legal_consents,
    serialize_mtproto_plans,
    serialize_mtproto_subscription,
    serialize_operators,
    serialize_vpn_products,
    serialize_user,
    serialize_vpn_subscription,
    serialize_vpn_subscription_item,
    serialize_whatsapp_plans,
    serialize_whatsapp_subscription,
    serialize_mtproto_subscription_item,
    serialize_whatsapp_subscription_item,
)
from app.bot.filters.is_admin import IsAdmin
from app.bot.utils.legal_consents import LEGAL_CONSENTS_VERSION
from app.bot.utils.validation import is_valid_client_count, is_valid_host, is_valid_path
from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.utils.constants import Currency, TransactionStatus
from app.bot.utils.navigation import NavSubscription, NavMTProto, NavWhatsApp
from app.db.models import BalanceLog, MTProtoSubscription, Server, Transaction, User, VPNSubscription, WhatsAppSubscription
from app.db.models.promocode import Promocode

logger = logging.getLogger(__name__)


def _services(request: Request) -> ServicesContainer:
    return request.app["services"]


def _config(request):
    return request.app["config"]


async def _serialize_vpn_subscription_items(user: User, services: ServicesContainer) -> list[dict]:
    subscriptions = await services.vpn.list_subscriptions(user)
    if not subscriptions:
        return []

    client_data_map, keys = await asyncio.gather(
        services.vpn.get_client_data_for_subscriptions(subscriptions),
        asyncio.gather(*[
            services.vpn.get_key_for_subscription(subscription)
            for subscription in subscriptions
        ]),
    )

    items: list[dict] = []
    for subscription, key in zip(subscriptions, keys, strict=False):
        client_data = client_data_map.get(subscription.id)
        current_profile = services.vpn.get_profile_for_subscription(subscription)
        available_profiles = services.vpn.get_available_profiles(
            subscription.server.location if subscription.server else None,
        )
        items.append(
            serialize_vpn_subscription_item(
                subscription_id=subscription.id,
                client_data=client_data,
                key=key,
                location=subscription.server.location if subscription.server else None,
                cancelled_at=subscription.cancelled_at,
                current_profile=current_profile,
                available_profiles=available_profiles,
            )
        )

    return items


async def _serialize_mtproto_subscription_items(tg_id: int, services: ServicesContainer, config) -> list[dict]:
    subscriptions = await services.mtproto.list_subscriptions(tg_id)
    if not subscriptions:
        return []

    links = await asyncio.gather(*[
        services.mtproto.get_link_for_subscription(subscription)
        for subscription in subscriptions
    ])

    return [
        serialize_mtproto_subscription_item(subscription, link, config.shop.MTPROTO_LOCATION)
        for subscription, link in zip(subscriptions, links, strict=False)
    ]


async def _serialize_whatsapp_subscription_items(tg_id: int, services: ServicesContainer, config) -> list[dict]:
    subscriptions = await services.whatsapp.list_subscriptions(tg_id)
    if not subscriptions:
        return []

    return [
        serialize_whatsapp_subscription_item(subscription, config.shop.WHATSAPP_HOST, config.shop.WHATSAPP_LOCATION)
        for subscription in subscriptions
    ]


async def handle_me(request: Request) -> Response:
    """GET /api/v1/me — User profile + subscription status overview."""
    user = request["user"]
    tg_id = request["tg_id"]
    services = _services(request)
    config = _config(request)

    # Run all checks in parallel for speed
    tasks = {
        "vpn_subscriptions": services.vpn.list_subscriptions(user),
        "vpn_trial": services.subscription.is_trial_available(user),
        "is_admin": IsAdmin()(user_id=tg_id),
    }
    if config.shop.MTPROTO_ENABLED:
        tasks["mtproto_active"] = services.mtproto.is_active(tg_id)
        tasks["mtproto_trial"] = services.mtproto.is_trial_available(tg_id)
    if config.shop.WHATSAPP_ENABLED:
        tasks["whatsapp_active"] = services.whatsapp.is_active(tg_id)
        tasks["whatsapp_trial"] = services.whatsapp.is_trial_available(tg_id)

    results = dict(zip(tasks.keys(), await asyncio.gather(*tasks.values())))

    vpn_subscriptions = results["vpn_subscriptions"]
    if vpn_subscriptions:
        vpn_client_data = await services.vpn.get_client_data_for_subscriptions(vpn_subscriptions)
        vpn_active = any(
            client_data is not None and not client_data.has_subscription_expired
            for client_data in vpn_client_data.values()
        )
    else:
        vpn_active = False

    data = serialize_user(
        user=user,
        vpn_active=vpn_active,
        mtproto_active=results.get("mtproto_active", False),
        whatsapp_active=results.get("whatsapp_active", False),
        vpn_trial_available=results["vpn_trial"],
        mtproto_trial_available=results.get("mtproto_trial", False),
        whatsapp_trial_available=results.get("whatsapp_trial", False),
    )
    data["features"] = {
        "mtproto_enabled": config.shop.MTPROTO_ENABLED,
        "whatsapp_enabled": config.shop.WHATSAPP_ENABLED,
        "stars_enabled": config.shop.PAYMENT_STARS_ENABLED,
    }
    data["is_admin"] = results["is_admin"]

    return web.json_response(data)


async def handle_health(request: Request) -> Response:
    """GET /api/v1/health — lightweight production health endpoint."""
    session_factory = request.app["session"]
    config = _config(request)

    try:
        async with session_factory() as session:
            await session.execute(select(1))
    except Exception as exception:  # noqa: BLE001
        logger.exception("Health check database probe failed: %s", exception)
        return web.json_response(
            {
                "status": "degraded",
                "checks": {
                    "database": {
                        "status": "failed",
                        "reason": str(exception),
                    }
                },
                "features": {
                    "mtproto_enabled": config.shop.MTPROTO_ENABLED,
                    "whatsapp_enabled": config.shop.WHATSAPP_ENABLED,
                },
            },
            status=503,
        )

    return web.json_response(
        {
            "status": "ok",
            "checks": {
                "database": {
                    "status": "passed",
                }
            },
            "features": {
                "mtproto_enabled": config.shop.MTPROTO_ENABLED,
                "whatsapp_enabled": config.shop.WHATSAPP_ENABLED,
            },
        }
    )


async def handle_operators(request: Request) -> Response:
    """GET /api/v1/operators — Available mobile operators."""
    services = _services(request)
    operators = services.product_catalog.get_operators()
    return web.json_response({"operators": serialize_operators(operators)})


async def handle_plans(request: Request) -> Response:
    """GET /api/v1/plans — VPN plans (all pricing)."""
    services = _services(request)
    catalog = services.product_catalog
    products = catalog.get_vpn_products()
    durations = catalog.get_durations()
    return web.json_response({"plans": serialize_vpn_products(products, durations)})


async def handle_plans_mtproto(request: Request) -> Response:
    """GET /api/v1/plans/mtproto — MTProto pricing."""
    config = _config(request)
    if not config.shop.MTPROTO_ENABLED:
        return web.json_response({"error": "MTProto is not enabled"}, status=404)
    return web.json_response({"plans": serialize_mtproto_plans(config)})


async def handle_plans_whatsapp(request: Request) -> Response:
    """GET /api/v1/plans/whatsapp — WhatsApp pricing."""
    config = _config(request)
    if not config.shop.WHATSAPP_ENABLED:
        return web.json_response({"error": "WhatsApp is not enabled"}, status=404)
    return web.json_response({"plans": serialize_whatsapp_plans(config)})


async def handle_subscription_vpn(request: Request) -> Response:
    """GET /api/v1/subscription — VPN subscription details."""
    user = request["user"]
    services = _services(request)

    subscription = await services.vpn.get_primary_subscription(user)
    if not subscription:
        return web.json_response(
            serialize_vpn_subscription(
                client_data=None,
                key=None,
                location=None,
                cancelled_at=None,
                current_profile=None,
                available_profiles=[],
                subscription_id=None,
            )
        )

    client_data, key = await asyncio.gather(
        services.vpn.get_client_data_for_subscription(subscription),
        services.vpn.get_key_for_subscription(subscription),
    )

    location = subscription.server.location if subscription.server else None
    current_profile = services.vpn.get_profile_for_subscription(subscription)
    available_profiles = services.vpn.get_available_profiles(location)
    return web.json_response(
        serialize_vpn_subscription(
            client_data,
            key,
            location,
            subscription.cancelled_at,
            current_profile=current_profile,
            available_profiles=available_profiles,
            subscription_id=subscription.id,
        )
    )


async def handle_subscription_vpn_profile(request: Request) -> Response:
    """POST /api/v1/subscription/vpn-profile — Switch active VPN profile."""
    user = request["user"]
    services = _services(request)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    profile_slug = body.get("profile_slug")
    if not isinstance(profile_slug, str) or not profile_slug:
        return web.json_response({"error": "profile_slug is required"}, status=400)

    subscription_id = body.get("subscription_id")
    if subscription_id is not None:
        if not isinstance(subscription_id, int):
            return web.json_response({"error": "subscription_id must be integer"}, status=400)
        subscription = await services.vpn.get_subscription(subscription_id)
    else:
        subscription = await services.vpn.get_primary_subscription(user)

    if not subscription:
        return web.json_response({"error": "VPN subscription not found"}, status=404)

    success = await services.vpn.change_vpn_profile(
        user=user,
        new_profile_slug=profile_slug,
        subscription_id=subscription.id,
    )
    if not success:
        return web.json_response({"error": "Failed to switch VPN profile"}, status=400)

    client_data, key = await asyncio.gather(
        services.vpn.get_client_data_for_subscription(subscription),
        services.vpn.get_key_for_subscription(subscription),
    )
    refreshed_subscription = await services.vpn.get_subscription(subscription.id)
    if not refreshed_subscription:
        return web.json_response({"error": "VPN subscription not found"}, status=404)

    location = refreshed_subscription.server.location if refreshed_subscription.server else None
    current_profile = services.vpn.get_profile_for_subscription(refreshed_subscription)
    available_profiles = services.vpn.get_available_profiles(location)
    return web.json_response(
        serialize_vpn_subscription(
            client_data,
            key,
            location,
            refreshed_subscription.cancelled_at,
            current_profile=current_profile,
            available_profiles=available_profiles,
            subscription_id=refreshed_subscription.id,
        )
    )


async def handle_legal_consents_accept(request: Request) -> Response:
    """POST /api/v1/legal-consents — Persist required legal consents and optional marketing opt-in."""
    user = request["user"]
    session_factory = request.app["session"]

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    privacy_policy = body.get("privacy_policy")
    terms_of_use = body.get("terms_of_use")
    personal_data = body.get("personal_data")
    marketing = body.get("marketing")

    if not all(isinstance(value, bool) for value in (privacy_policy, terms_of_use, personal_data, marketing)):
        return web.json_response(
            {
                "error": "privacy_policy, terms_of_use, personal_data and marketing must be boolean",
            },
            status=400,
        )

    if not privacy_policy or not terms_of_use or not personal_data:
        return web.json_response(
            {
                "error": "Required consents must be accepted",
            },
            status=400,
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    update_payload = {
        "legal_consents_version": LEGAL_CONSENTS_VERSION,
        "privacy_policy_accepted_at": user.privacy_policy_accepted_at or now,
        "terms_of_use_accepted_at": user.terms_of_use_accepted_at or now,
        "personal_data_consent_accepted_at": user.personal_data_consent_accepted_at or now,
        "marketing_consent_granted": marketing,
        "marketing_consent_updated_at": now,
    }

    async with session_factory() as session:
        await User.update(session=session, tg_id=user.tg_id, **update_payload)
        refreshed_user = await User.get(session=session, tg_id=user.tg_id)

    if not refreshed_user:
        return web.json_response({"error": "User not found"}, status=404)

    return web.json_response({"legal_consents": serialize_legal_consents(refreshed_user)})


async def handle_subscription_mtproto(request: Request) -> Response:
    """GET /api/v1/subscription/mtproto — MTProto subscription."""
    tg_id = request["tg_id"]
    config = _config(request)
    services = _services(request)

    if not config.shop.MTPROTO_ENABLED:
        return web.json_response({"error": "MTProto is not enabled"}, status=404)

    sub = await services.mtproto.get_subscription(tg_id)
    link = await services.mtproto.get_link(tg_id) if sub else None

    return web.json_response(
        serialize_mtproto_subscription(
            sub,
            link,
            config.shop.MTPROTO_LOCATION,
            subscription_id=sub.id if sub else None,
        )
    )


async def handle_subscription_whatsapp(request: Request) -> Response:
    """GET /api/v1/subscription/whatsapp — WhatsApp subscription."""
    tg_id = request["tg_id"]
    config = _config(request)
    services = _services(request)

    if not config.shop.WHATSAPP_ENABLED:
        return web.json_response({"error": "WhatsApp is not enabled"}, status=404)

    sub = await services.whatsapp.get_subscription(tg_id)

    return web.json_response(
        serialize_whatsapp_subscription(
            sub,
            config.shop.WHATSAPP_HOST,
            config.shop.WHATSAPP_LOCATION,
            subscription_id=sub.id if sub else None,
        )
    )


async def handle_subscriptions(request: Request) -> Response:
    """GET /api/v1/subscriptions — All subscription instances grouped by product."""
    user = request["user"]
    tg_id = request["tg_id"]
    config = _config(request)
    services = _services(request)

    vpn_task = _serialize_vpn_subscription_items(user, services)
    mtproto_task = (
        _serialize_mtproto_subscription_items(tg_id, services, config)
        if config.shop.MTPROTO_ENABLED
        else asyncio.sleep(0, result=[])
    )
    whatsapp_task = (
        _serialize_whatsapp_subscription_items(tg_id, services, config)
        if config.shop.WHATSAPP_ENABLED
        else asyncio.sleep(0, result=[])
    )

    vpn_items, mtproto_items, whatsapp_items = await asyncio.gather(
        vpn_task,
        mtproto_task,
        whatsapp_task,
    )

    return web.json_response({
        "vpn": vpn_items,
        "mtproto": mtproto_items,
        "whatsapp": whatsapp_items,
    })


async def handle_vpn_subscriptions(request: Request) -> Response:
    user = request["user"]
    services = _services(request)
    return web.json_response({"subscriptions": await _serialize_vpn_subscription_items(user, services)})


async def handle_mtproto_subscriptions(request: Request) -> Response:
    tg_id = request["tg_id"]
    config = _config(request)
    services = _services(request)
    if not config.shop.MTPROTO_ENABLED:
        return web.json_response({"subscriptions": []})
    return web.json_response({
        "subscriptions": await _serialize_mtproto_subscription_items(tg_id, services, config),
    })


async def handle_whatsapp_subscriptions(request: Request) -> Response:
    tg_id = request["tg_id"]
    config = _config(request)
    services = _services(request)
    if not config.shop.WHATSAPP_ENABLED:
        return web.json_response({"subscriptions": []})
    return web.json_response({
        "subscriptions": await _serialize_whatsapp_subscription_items(tg_id, services, config),
    })


async def handle_payment_invoice(request: Request) -> Response:
    """POST /api/v1/payment/invoice — Create payment link (Stars or T-Bank).

    Body: {"product": "vpn|mtproto|whatsapp", "devices": 3, "duration": 30, "is_extend": false, "currency": "stars"|"rub"}
    """
    user = request["user"]
    tg_id = request["tg_id"]
    services = _services(request)
    config = _config(request)
    bot = request.app["bot"]

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    product = body.get("product", "vpn")
    duration = body.get("duration")
    devices = body.get("devices", 1)
    is_extend = body.get("is_extend", False)
    currency_choice = body.get("currency", "stars")  # "stars" or "rub"

    if not duration or not isinstance(duration, int) or duration <= 0:
        return web.json_response({"error": "Invalid duration"}, status=400)

    catalog = services.product_catalog
    use_rub = currency_choice == "rub" and config.shop.PAYMENT_TBANK_ENABLED

    # Determine currency code for price lookup
    price_currency = Currency.RUB.code if use_rub else Currency.XTR.code

    # Determine price and product info
    if product == "vpn":
        vpn_product = catalog.get_vpn_product_by_devices(devices)
        if not vpn_product:
            return web.json_response({"error": "Plan not found"}, status=404)
        price = catalog.get_price(vpn_product.slug, price_currency, duration)
        if price is None:
            return web.json_response({"error": "Invalid duration for this plan"}, status=400)
        amount = int(price) if not use_rub else float(price)
        product_type = "vpn"

    elif product == "mtproto":
        if not config.shop.MTPROTO_ENABLED:
            return web.json_response({"error": "MTProto is not enabled"}, status=404)
        if use_rub:
            amount = services.mtproto.get_price(duration)
        else:
            amount = services.mtproto.get_price_stars(duration)
        if amount is None:
            return web.json_response({"error": "Invalid duration"}, status=400)
        amount = float(amount)
        devices = 1
        product_type = "mtproto"

    elif product == "whatsapp":
        if not config.shop.WHATSAPP_ENABLED:
            return web.json_response({"error": "WhatsApp is not enabled"}, status=404)
        if use_rub:
            amount = services.whatsapp.get_price(duration)
        else:
            amount = services.whatsapp.get_price_stars(duration)
        if amount is None:
            return web.json_response({"error": "Invalid duration"}, status=400)
        amount = float(amount)
        devices = 1
        product_type = "whatsapp"

    elif product.startswith("bundle_"):
        if not (config.shop.MTPROTO_ENABLED and config.shop.WHATSAPP_ENABLED):
            return web.json_response({"error": "Bundles require MTProto and WhatsApp"}, status=404)
        bundle_product = catalog.get_product(product)
        if not bundle_product or not bundle_product.is_bundle:
            return web.json_response({"error": "Invalid bundle"}, status=400)
        amount = catalog.calculate_price_stars(product, duration)
        devices = 1
        product_type = product

    else:
        return web.json_response({"error": "Invalid product type"}, status=400)

    # --- T-Bank (RUB) payment flow ---
    if use_rub:
        gateway_factory = request.app.get("gateway_factory")
        if not gateway_factory:
            return web.json_response({"error": "Payment gateway not available"}, status=500)

        try:
            gateway = gateway_factory.get_gateway(NavSubscription.PAY_TBANK)
        except ValueError:
            return web.json_response({"error": "T-Bank gateway not registered"}, status=500)

        sub_data = SubscriptionData(
            state=NavSubscription.PAY_TBANK,
            is_extend=is_extend,
            is_change=False,
            user_id=tg_id,
            devices=devices,
            duration=duration,
            price=float(amount),
            product_type=product_type,
        )

        try:
            payment_url = await gateway.create_payment(sub_data)
        except Exception as e:
            logger.error(f"Failed to create T-Bank payment: {e}")
            return web.json_response({"error": "Failed to create payment"}, status=500)

        logger.info(f"T-Bank payment created for user {tg_id}: {payment_url}")
        return web.json_response({"payment_url": payment_url})

    # --- Stars payment flow ---
    sub_data = SubscriptionData(
        state=NavSubscription.PAY_TELEGRAM_STARS,
        is_extend=is_extend,
        is_change=False,
        user_id=tg_id,
        devices=devices,
        duration=duration,
        price=float(amount),
        product_type=product_type,
    )
    payload = sub_data.pack()

    # Create transaction
    payment_id = str(uuid.uuid4())
    session_factory = request.app["session"]
    async with session_factory() as session:
        await Transaction.create(
            session=session,
            payment_id=payment_id,
            tg_id=tg_id,
            subscription=payload,
            status=TransactionStatus.PENDING,
        )

    # Dev users pay 1 star
    from app.bot.filters.is_dev import IsDev
    if await IsDev()(user_id=tg_id):
        amount = 1

    prices = [LabeledPrice(label=Currency.XTR.code, amount=int(amount))]
    try:
        invoice_url = await bot.create_invoice_link(
            title=f"{product_type} / {duration} days",
            description=f"Subscription for {duration} days",
            prices=prices,
            payload=payload,
            currency=Currency.XTR.code,
        )
    except Exception as e:
        logger.error(f"Failed to create invoice: {e}")
        return web.json_response({"error": "Failed to create invoice"}, status=500)

    logger.info(f"Invoice created for user {tg_id}: {invoice_url}")
    return web.json_response({"invoice_url": invoice_url})


async def handle_trial_vpn(request: Request) -> Response:
    """POST /api/v1/trial/vpn — Activate VPN trial."""
    user = request["user"]
    services = _services(request)

    success = await services.subscription.gift_trial(user)
    if not success:
        return web.json_response({"error": "Trial not available"}, status=400)

    key = await services.vpn.get_key(user)
    return web.json_response({"success": True, "key": key})


async def handle_trial_mtproto(request: Request) -> Response:
    """POST /api/v1/trial/mtproto — Activate MTProto trial."""
    tg_id = request["tg_id"]
    config = _config(request)
    services = _services(request)

    if not config.shop.MTPROTO_ENABLED:
        return web.json_response({"error": "MTProto is not enabled"}, status=404)

    if not await services.mtproto.is_trial_available(tg_id):
        return web.json_response({"error": "Trial not available"}, status=400)

    secret = await services.mtproto.activate(
        user_tg_id=tg_id,
        duration_days=config.shop.MTPROTO_TRIAL_PERIOD,
        is_trial=True,
    )

    if not secret:
        return web.json_response({"error": "Failed to activate trial"}, status=500)

    link = await services.mtproto.get_link(tg_id)
    return web.json_response({"success": True, "link": link})


async def handle_trial_whatsapp(request: Request) -> Response:
    """POST /api/v1/trial/whatsapp — Activate WhatsApp trial."""
    tg_id = request["tg_id"]
    config = _config(request)
    services = _services(request)

    if not config.shop.WHATSAPP_ENABLED:
        return web.json_response({"error": "WhatsApp is not enabled"}, status=404)

    if not await services.whatsapp.is_trial_available(tg_id):
        return web.json_response({"error": "Trial not available"}, status=400)

    port = await services.whatsapp.activate(
        user_tg_id=tg_id,
        duration_days=config.shop.WHATSAPP_TRIAL_PERIOD,
        is_trial=True,
    )

    if not port:
        return web.json_response({"error": "Failed to activate trial"}, status=500)

    return web.json_response({
        "success": True,
        "host": config.shop.WHATSAPP_HOST,
        "port": port,
    })


async def handle_plans_bundles(request: Request) -> Response:
    """GET /api/v1/plans/bundles — Bundle products with pricing."""
    config = _config(request)
    services = _services(request)

    if not (config.shop.MTPROTO_ENABLED and config.shop.WHATSAPP_ENABLED):
        return web.json_response({"error": "Bundles require MTProto and WhatsApp enabled"}, status=404)

    return web.json_response({"plans": serialize_bundle_plans(services.product_catalog)})


async def handle_trial_bundle(request: Request) -> Response:
    """POST /api/v1/trial/bundle — Activate bundle trial.

    Body: {"slug": "bundle_msg"}
    """
    user = request["user"]
    tg_id = request["tg_id"]
    config = _config(request)
    services = _services(request)

    if not (config.shop.MTPROTO_ENABLED and config.shop.WHATSAPP_ENABLED):
        return web.json_response({"error": "Bundles require MTProto and WhatsApp enabled"}, status=404)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    slug = body.get("slug", "bundle_msg")
    product = services.product_catalog.get_product(slug)
    if not product or not product.is_bundle:
        return web.json_response({"error": "Invalid bundle slug"}, status=400)

    # Check trial availability for all components
    for component in product.includes:
        if component == "mtproto":
            if not await services.mtproto.is_trial_available(tg_id):
                return web.json_response({"error": "Trial not available"}, status=400)
        elif component == "socks5":
            if not await services.whatsapp.is_trial_available(tg_id):
                return web.json_response({"error": "Trial not available"}, status=400)

    results = await services.bundle.activate(
        slug=slug,
        user_tg_id=tg_id,
        user=user,
        duration=product.trial_days,
        is_trial=True,
    )

    all_success = all(r.get("success", False) for r in results.values())
    if not all_success:
        return web.json_response({"error": "Failed to activate bundle trial", "details": results}, status=500)

    return web.json_response({"success": True, "slug": slug, "trial_days": product.trial_days})


async def handle_promocode_activate(request: Request) -> Response:
    """POST /api/v1/promocode/activate — Activate a promocode for VPN subscription.

    Body: {"code": "ABC123"}
    """
    user = request["user"]
    services = _services(request)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    code = body.get("code", "").strip()
    if not code:
        return web.json_response({"error": "Промокод не указан"}, status=400)

    session_factory = request.app["session"]
    async with session_factory() as session:
        promocode = await Promocode.get(session=session, code=code)

    if not promocode:
        return web.json_response({"error": "Неверный или использованный промокод"}, status=400)

    if promocode.is_fully_used:
        return web.json_response({"error": "Неверный или использованный промокод"}, status=400)

    success = await services.vpn.activate_promocode(user, promocode)
    if not success:
        return web.json_response({"error": "Не удалось активировать промокод"}, status=500)

    logger.info(f"Promocode {code} activated via Mini App for user {user.tg_id}")
    return web.json_response({"success": True, "duration": promocode.duration})


# ---------- Balance endpoints ----------


STARS_RATE = 1.8  # 1 Star ≈ 1.8 RUB
TOPUP_AMOUNTS = [250, 500, 1000, 2000]  # allowed top-up amounts in RUB


async def handle_balance_topup(request: Request) -> Response:
    """POST /api/v1/balance/topup — Create top-up invoice (Stars or T-Bank).

    Body: {"amount": 500, "currency": "stars" | "rub"}
    amount — sum in rubles (integer)
    """
    user = request["user"]
    tg_id = request["tg_id"]
    config = _config(request)
    bot = request.app["bot"]

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    amount = body.get("amount")
    currency_choice = body.get("currency", "stars")

    if not amount or not isinstance(amount, int) or amount <= 0:
        return web.json_response({"error": "Invalid amount"}, status=400)

    if amount not in TOPUP_AMOUNTS:
        return web.json_response(
            {"error": f"Amount must be one of {TOPUP_AMOUNTS}"}, status=400
        )

    # --- Stars flow ---
    if currency_choice == "stars":
        stars_amount = max(1, round(amount / STARS_RATE))

        # Dev users pay 1 star
        from app.bot.filters.is_dev import IsDev
        if await IsDev()(user_id=tg_id):
            stars_amount = 1

        prices = [LabeledPrice(label="XTR", amount=stars_amount)]
        try:
            invoice_url = await bot.create_invoice_link(
                title=f"Top-up {amount}₽",
                description=f"Balance top-up: {amount} RUB",
                prices=prices,
                payload=f"topup:{amount}",
                currency="XTR",
            )
        except Exception as e:
            logger.error(f"Failed to create top-up invoice: {e}")
            return web.json_response({"error": "Failed to create invoice"}, status=500)

        logger.info(f"Top-up invoice created for user {tg_id}: {amount}₽ = {stars_amount}★")
        return web.json_response({"invoice_url": invoice_url, "stars_amount": stars_amount})

    # --- T-Bank (Card / SBP) flow ---
    if currency_choice in ("rub", "sbp"):
        gateway_factory = request.app.get("gateway_factory")
        if not gateway_factory:
            return web.json_response({"error": "Payment gateway not available"}, status=500)

        nav_state = (
            NavSubscription.PAY_TBANK_SBP if currency_choice == "sbp"
            else NavSubscription.PAY_TBANK
        )

        try:
            gateway = gateway_factory.get_gateway(nav_state)
        except ValueError:
            return web.json_response({"error": "Payment gateway not registered"}, status=500)

        sub_data = SubscriptionData(
            state=nav_state,
            is_extend=False,
            is_change=False,
            user_id=tg_id,
            devices=0,
            duration=0,
            price=float(amount),
            product_type="topup",
        )

        try:
            payment_url = await gateway.create_payment(sub_data)
        except Exception as e:
            logger.error(f"Failed to create top-up payment ({currency_choice}): {e}")
            return web.json_response({"error": "Failed to create payment"}, status=500)

        logger.info(f"Top-up payment created ({currency_choice}) for user {tg_id}: {amount}₽")
        return web.json_response({"payment_url": payment_url})

    return web.json_response({"error": "Invalid currency"}, status=400)


async def handle_balance_buy(request: Request) -> Response:
    """POST /api/v1/plans/buy — Purchase a plan from balance.

    Body: {"product": "vpn", "devices": 1, "duration": 30, "location": "Amsterdam"}
    """
    user = request["user"]
    tg_id = request["tg_id"]
    services = _services(request)
    config = _config(request)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    product = body.get("product", "vpn")
    duration = body.get("duration")
    devices = body.get("devices", 1)
    location = body.get("location")

    if not duration or not isinstance(duration, int) or duration <= 0:
        return web.json_response({"error": "Invalid duration"}, status=400)

    catalog = services.product_catalog

    # Calculate price in kopecks
    if product == "vpn":
        vpn_product = catalog.get_vpn_product_by_devices(devices)
        if not vpn_product:
            return web.json_response({"error": "Plan not found"}, status=404)
        price_rub = catalog.get_price(vpn_product.slug, Currency.RUB.code, duration)
        if price_rub is None:
            return web.json_response({"error": "Invalid duration for this plan"}, status=400)
        price_kopecks = int(round(float(price_rub) * 100))
        description = f"VPN {devices} dev / {duration}d"

    elif product == "mtproto":
        if not config.shop.MTPROTO_ENABLED:
            return web.json_response({"error": "MTProto is not enabled"}, status=404)
        price_rub = services.mtproto.get_price(duration)
        if price_rub is None:
            return web.json_response({"error": "Invalid duration"}, status=400)
        price_kopecks = int(round(float(price_rub) * 100))
        devices = 1
        description = f"MTProto / {duration}d"

    elif product == "whatsapp":
        if not config.shop.WHATSAPP_ENABLED:
            return web.json_response({"error": "WhatsApp is not enabled"}, status=404)
        price_rub = services.whatsapp.get_price(duration)
        if price_rub is None:
            return web.json_response({"error": "Invalid duration"}, status=400)
        price_kopecks = int(round(float(price_rub) * 100))
        devices = 1
        description = f"WhatsApp / {duration}d"

    else:
        return web.json_response({"error": "Invalid product type"}, status=400)

    # Check balance
    if user.balance < price_kopecks:
        return web.json_response(
            {
                "error": "Insufficient balance",
                "required": price_kopecks / 100,
                "balance": user.balance / 100,
            },
            status=400,
        )

    # Atomic deduction + activation
    session_factory = request.app["session"]
    async with session_factory() as session:
        # Re-fetch user inside session for atomicity
        db_user = await User.get(session=session, tg_id=tg_id)
        if db_user.balance < price_kopecks:
            return web.json_response({"error": "Insufficient balance"}, status=400)

        await User.update(session=session, tg_id=tg_id, balance=db_user.balance - price_kopecks)

        await BalanceLog.create(
            session=session,
            tg_id=tg_id,
            amount=-price_kopecks,
            type="purchase",
            description=description,
        )

    # Activate a new subscription instance.
    if product == "vpn":
        created = await services.vpn.create_subscription(
            user=user,
            devices=devices,
            duration=duration,
            location=location,
        )
        if not created:
            return web.json_response({"error": "Failed to create VPN subscription"}, status=500)

    elif product == "mtproto":
        secret = await services.mtproto.activate(tg_id, duration)
        if not secret:
            return web.json_response({"error": "Failed to create MTProto subscription"}, status=500)

    elif product == "whatsapp":
        port = await services.whatsapp.activate(tg_id, duration)
        if not port:
            return web.json_response({"error": "Failed to create WhatsApp subscription"}, status=500)

    logger.info(
        f"Balance purchase: user={tg_id}, product={product}, "
        f"duration={duration}d, price={price_kopecks/100}₽"
    )

    return web.json_response({"success": True, "product": product, "duration": duration})


async def handle_balance_auto_renew(request: Request) -> Response:
    """POST /api/v1/balance/auto-renew — Toggle auto-renewal.

    Body: {"enabled": true | false}
    """
    tg_id = request["tg_id"]

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        return web.json_response({"error": "enabled must be boolean"}, status=400)

    session_factory = request.app["session"]
    async with session_factory() as session:
        await User.update(session=session, tg_id=tg_id, auto_renew=enabled)

    logger.info(f"Auto-renew {'enabled' if enabled else 'disabled'} for user {tg_id}")
    return web.json_response({"auto_renew": enabled})


# ---------- Cancel subscription ----------


async def handle_subscription_cancel(request: Request) -> Response:
    """POST /api/v1/subscription/cancel — Cancel a subscription (disable auto-renew).

    Body: {"product": "vpn" | "mtproto" | "whatsapp"}
    The subscription stays active until the end of the paid period.
    """
    user = request["user"]
    tg_id = request["tg_id"]
    config = _config(request)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    product = body.get("product")
    if product not in ("vpn", "mtproto", "whatsapp"):
        return web.json_response({"error": "Invalid product"}, status=400)

    subscription_id = body.get("subscription_id")
    if subscription_id is not None and not isinstance(subscription_id, int):
        return web.json_response({"error": "subscription_id must be integer"}, status=400)

    session_factory = request.app["session"]

    if product == "vpn":
        async with session_factory() as session:
            if subscription_id is None:
                subscription = await services.vpn.get_primary_subscription(user)
            else:
                subscription = await services.vpn.get_subscription(subscription_id)
            if not subscription:
                return web.json_response({"error": "VPN subscription not found"}, status=404)

            updated = await VPNSubscription.cancel(session=session, subscription_id=subscription.id)
            if updated and updated.vpn_id == user.vpn_id:
                await User.update(session=session, tg_id=tg_id, vpn_cancelled_at=updated.cancelled_at)
                user.vpn_cancelled_at = updated.cancelled_at

        if not updated:
            return web.json_response({"error": "VPN subscription not found"}, status=404)
        return web.json_response({
            "success": True,
            "product": "vpn",
            "subscription_id": updated.id,
        })

    if product == "mtproto":
        if not config.shop.MTPROTO_ENABLED:
            return web.json_response({"error": "MTProto is not enabled"}, status=404)
        async with session_factory() as session:
            sub = await MTProtoSubscription.cancel(
                session=session,
                user_tg_id=tg_id,
                subscription_id=subscription_id,
            )
        if not sub:
            return web.json_response({"error": "MTProto subscription not found"}, status=404)
        return web.json_response({
            "success": True,
            "product": "mtproto",
            "subscription_id": sub.id,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        })

    if product == "whatsapp":
        if not config.shop.WHATSAPP_ENABLED:
            return web.json_response({"error": "WhatsApp is not enabled"}, status=404)
        async with session_factory() as session:
            sub = await WhatsAppSubscription.cancel(
                session=session,
                user_tg_id=tg_id,
                subscription_id=subscription_id,
            )
        if not sub:
            return web.json_response({"error": "WhatsApp subscription not found"}, status=404)
        return web.json_response({
            "success": True,
            "product": "whatsapp",
            "subscription_id": sub.id,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        })


# ---------- Locations ----------


async def handle_locations(request: Request) -> Response:
    """GET /api/v1/locations — Available server locations."""
    services = _services(request)
    locations = await services.server_pool.get_locations()
    return web.json_response({"locations": locations})


# ---------- Admin endpoints ----------


async def handle_admin_auth(request: Request) -> Response:
    """POST /api/v1/admin/auth — Authenticate via Telegram Login Widget.

    Body: { id, first_name, username?, auth_date, hash, ... }
    Returns: { token, expires_in, user: { tg_id, first_name, username } }
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    # Validate required fields
    tg_id = body.get("id")
    if not tg_id:
        return web.json_response({"error": "Missing id"}, status=400)

    try:
        tg_id = int(tg_id)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid id"}, status=400)

    bot_token = _config(request).bot.TOKEN

    # Validate Telegram Login Widget data
    if not _validate_telegram_login(body, bot_token):
        return web.json_response({"error": "Invalid Telegram login data"}, status=401)

    # Check admin status
    if not await IsAdmin()(user_id=tg_id):
        return web.json_response({"error": "Admin access required"}, status=403)

    # Generate admin token
    token = _create_admin_token(tg_id, bot_token)

    return web.json_response({
        "token": token,
        "expires_in": 86400,
        "user": {
            "tg_id": tg_id,
            "first_name": body.get("first_name", ""),
            "username": body.get("username"),
        },
    })


async def handle_admin_stats(request: Request) -> Response:
    """GET /api/v1/admin/stats — Dashboard statistics."""
    await require_admin(request)

    session_factory = request.app["session"]
    services = _services(request)

    async with session_factory() as session:
        # Total users
        result = await session.execute(select(func.count(User.id)))
        total_users = result.scalar() or 0

        # Registrations last 30 days
        result = await session.execute(
            select(
                func.date(User.created_at).label("date"),
                func.count(User.id).label("count"),
            )
            .where(User.created_at >= func.date("now", "-30 days"))
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )
        registrations_30d = [
            {"date": str(row.date), "count": row.count} for row in result.all()
        ]

        # Payments last 30 days (completed)
        result = await session.execute(
            select(
                func.date(Transaction.created_at).label("date"),
                func.count(Transaction.id).label("count"),
            )
            .where(
                Transaction.status == TransactionStatus.COMPLETED,
                Transaction.created_at >= func.date("now", "-30 days"),
            )
            .group_by(func.date(Transaction.created_at))
            .order_by(func.date(Transaction.created_at))
        )
        payments_30d = [
            {"date": str(row.date), "count": row.count} for row in result.all()
        ]

    # Revenue via PaymentStatsService
    payment_method_currencies = {"stars": "XTR", "telegram_stars": "XTR"}
    revenue = await services.payment_stats.get_total_revenue_stats(
        payment_method_currencies=payment_method_currencies,
    )

    return web.json_response({
        "total_users": total_users,
        "active_subscriptions": 0,  # WIP: needs 3X-UI aggregation
        "revenue": revenue,
        "registrations_30d": registrations_30d,
        "payments_30d": payments_30d,
    })


async def handle_admin_users(request: Request) -> Response:
    """GET /api/v1/admin/users — Paginated user list with search."""
    await require_admin(request)

    q = request.query.get("q", "").strip()
    page = max(1, int(request.query.get("page", "1")))
    limit = min(100, max(1, int(request.query.get("limit", "20"))))
    offset = (page - 1) * limit

    session_factory = request.app["session"]
    async with session_factory() as session:
        base_query = select(User).options(selectinload(User.server))
        count_query = select(func.count(User.id))

        if q:
            # Search by tg_id (exact), username (ILIKE), first_name (ILIKE)
            conditions = [
                User.username.ilike(f"%{q}%"),
                User.first_name.ilike(f"%{q}%"),
            ]
            # If query is numeric, also try exact tg_id match
            if q.isdigit():
                conditions.append(User.tg_id == int(q))
            filter_clause = or_(*conditions)
            base_query = base_query.where(filter_clause)
            count_query = count_query.where(filter_clause)

        result = await session.execute(count_query)
        total = result.scalar() or 0

        result = await session.execute(
            base_query.order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
        users = result.scalars().all()

    return web.json_response({
        "users": [serialize_admin_user(u) for u in users],
        "total": total,
        "page": page,
        "limit": limit,
    })


async def handle_admin_user_detail(request: Request) -> Response:
    """GET /api/v1/admin/users/{tg_id} — User detail with VPN + transactions."""
    await require_admin(request)

    try:
        target_tg_id = int(request.match_info["tg_id"])
    except (KeyError, ValueError):
        return web.json_response({"error": "Invalid tg_id"}, status=400)

    session_factory = request.app["session"]
    services = _services(request)

    async with session_factory() as session:
        user = await User.get(session=session, tg_id=target_tg_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)

        transactions = await Transaction.get_by_user(session=session, tg_id=target_tg_id)

    # VPN client data
    client_data = await services.vpn.get_client_data(user)

    return web.json_response(
        serialize_admin_user_detail(user, client_data, transactions)
    )


async def handle_admin_servers(request: Request) -> Response:
    """GET /api/v1/admin/servers — All servers with client counts."""
    await require_admin(request)

    session_factory = request.app["session"]
    async with session_factory() as session:
        servers = await Server.get_all(session=session)

    return web.json_response({
        "servers": [serialize_admin_server(s) for s in servers],
    })


def _normalize_optional_string(value, *, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Expected string value")
    normalized = value.strip()
    if not normalized:
        return None
    if max_length is not None and len(normalized) > max_length:
        raise ValueError(f"String exceeds max length {max_length}")
    return normalized


async def handle_admin_server_update(request: Request) -> Response:
    """PATCH /api/v1/admin/servers/{server_id} — Update per-server VPN settings."""
    await require_admin(request)

    server_id_raw = request.match_info.get("server_id")
    try:
        server_id = int(server_id_raw)
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid server id"}, status=400)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    if not isinstance(body, dict):
        return web.json_response({"error": "Body must be an object"}, status=400)

    updates: dict[str, object] = {}
    try:
        if "host" in body:
            host = _normalize_optional_string(body.get("host"), max_length=255)
            if host is None or not is_valid_host(host):
                return web.json_response({"error": "Invalid panel host"}, status=400)
            updates["host"] = host

        if "location" in body:
            updates["location"] = _normalize_optional_string(body.get("location"), max_length=32)

        if "max_clients" in body:
            max_clients = body.get("max_clients")
            max_clients_str = str(max_clients)
            if not is_valid_client_count(max_clients_str):
                return web.json_response({"error": "Invalid max_clients"}, status=400)
            updates["max_clients"] = int(max_clients)

        if "subscription_host" in body:
            subscription_host = _normalize_optional_string(body.get("subscription_host"), max_length=255)
            if subscription_host is not None and not is_valid_host(subscription_host):
                return web.json_response({"error": "Invalid subscription host"}, status=400)
            updates["subscription_host"] = subscription_host

        if "subscription_port" in body:
            subscription_port = body.get("subscription_port")
            if subscription_port in ("", None):
                updates["subscription_port"] = None
            elif not isinstance(subscription_port, int) or not (1 <= subscription_port <= 65535):
                return web.json_response({"error": "Invalid subscription port"}, status=400)
            else:
                updates["subscription_port"] = subscription_port

        if "subscription_path" in body:
            subscription_path = _normalize_optional_string(body.get("subscription_path"), max_length=255)
            if subscription_path is not None and not is_valid_path(subscription_path):
                return web.json_response({"error": "Invalid subscription path"}, status=400)
            updates["subscription_path"] = subscription_path

        if "inbound_remark" in body:
            updates["inbound_remark"] = _normalize_optional_string(
                body.get("inbound_remark"),
                max_length=255,
            )

        if "client_flow" in body:
            updates["client_flow"] = _normalize_optional_string(
                body.get("client_flow"),
                max_length=128,
            )
    except ValueError as exception:
        return web.json_response({"error": str(exception)}, status=400)

    if not updates:
        return web.json_response({"error": "No valid fields to update"}, status=400)

    session_factory = request.app["session"]
    services = _services(request)

    async with session_factory() as session:
        server = await Server.get_by_id(session=session, id=server_id)
        if not server:
            return web.json_response({"error": "Server not found"}, status=404)

        previous_host = server.host
        await Server.update(session=session, name=server.name, **updates)
        updated_server = await Server.get_by_id(session=session, id=server_id)

    if previous_host != updated_server.host:
        await services.server_pool.refresh_server(updated_server)

    return web.json_response({"server": serialize_admin_server(updated_server)})


def register_routes(app: Application) -> None:
    """Register all API v1 routes."""
    app.router.add_get("/api/v1/health", handle_health)
    app.router.add_get("/api/v1/me", handle_me)
    app.router.add_get("/api/v1/operators", handle_operators)
    app.router.add_get("/api/v1/plans", handle_plans)
    app.router.add_get("/api/v1/plans/mtproto", handle_plans_mtproto)
    app.router.add_get("/api/v1/plans/whatsapp", handle_plans_whatsapp)
    app.router.add_get("/api/v1/subscription", handle_subscription_vpn)
    app.router.add_get("/api/v1/subscriptions", handle_subscriptions)
    app.router.add_get("/api/v1/subscriptions/vpn", handle_vpn_subscriptions)
    app.router.add_get("/api/v1/subscriptions/mtproto", handle_mtproto_subscriptions)
    app.router.add_get("/api/v1/subscriptions/whatsapp", handle_whatsapp_subscriptions)
    app.router.add_post("/api/v1/subscription/vpn-profile", handle_subscription_vpn_profile)
    app.router.add_post("/api/v1/legal-consents", handle_legal_consents_accept)
    app.router.add_get("/api/v1/subscription/mtproto", handle_subscription_mtproto)
    app.router.add_get("/api/v1/subscription/whatsapp", handle_subscription_whatsapp)
    app.router.add_post("/api/v1/payment/invoice", handle_payment_invoice)
    app.router.add_post("/api/v1/trial/vpn", handle_trial_vpn)
    app.router.add_post("/api/v1/trial/mtproto", handle_trial_mtproto)
    app.router.add_post("/api/v1/trial/whatsapp", handle_trial_whatsapp)
    app.router.add_get("/api/v1/plans/bundles", handle_plans_bundles)
    app.router.add_post("/api/v1/trial/bundle", handle_trial_bundle)
    app.router.add_post("/api/v1/promocode/activate", handle_promocode_activate)

    # Balance endpoints
    app.router.add_post("/api/v1/balance/topup", handle_balance_topup)
    app.router.add_post("/api/v1/plans/buy", handle_balance_buy)
    app.router.add_post("/api/v1/balance/auto-renew", handle_balance_auto_renew)

    # Cancel subscription
    app.router.add_post("/api/v1/subscription/cancel", handle_subscription_cancel)

    # Locations
    app.router.add_get("/api/v1/locations", handle_locations)

    # Admin endpoints
    app.router.add_post("/api/v1/admin/auth", handle_admin_auth)
    app.router.add_get("/api/v1/admin/stats", handle_admin_stats)
    app.router.add_get("/api/v1/admin/users", handle_admin_users)
    app.router.add_get("/api/v1/admin/users/{tg_id}", handle_admin_user_detail)
    app.router.add_get("/api/v1/admin/servers", handle_admin_servers)
    app.router.add_patch("/api/v1/admin/servers/{server_id}", handle_admin_server_update)
