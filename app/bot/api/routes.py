import logging
import uuid

from aiohttp import web
from aiohttp.web import Application, Request, Response

from aiogram.types import LabeledPrice

from app.bot.api.serializers import (
    serialize_mtproto_plans,
    serialize_mtproto_subscription,
    serialize_plans,
    serialize_user,
    serialize_vpn_subscription,
    serialize_whatsapp_plans,
    serialize_whatsapp_subscription,
)
from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.utils.constants import Currency, TransactionStatus
from app.bot.utils.navigation import NavSubscription, NavMTProto, NavWhatsApp
from app.db.models import Transaction

logger = logging.getLogger(__name__)


def _services(request: Request) -> ServicesContainer:
    return request.app["services"]


def _config(request):
    return request.app["config"]


async def handle_me(request: Request) -> Response:
    """GET /api/v1/me — User profile + subscription status overview."""
    user = request["user"]
    tg_id = request["tg_id"]
    services = _services(request)
    config = _config(request)

    # Check VPN status
    client_data = await services.vpn.get_client_data(user)
    vpn_active = client_data is not None and not client_data.has_subscription_expired

    # Check MTProto status
    mtproto_active = False
    if config.shop.MTPROTO_ENABLED:
        mtproto_active = await services.mtproto.is_active(tg_id)

    # Check WhatsApp status
    whatsapp_active = False
    if config.shop.WHATSAPP_ENABLED:
        whatsapp_active = await services.whatsapp.is_active(tg_id)

    # Check trial availability
    vpn_trial = await services.subscription.is_trial_available(user)
    mtproto_trial = (
        await services.mtproto.is_trial_available(tg_id) if config.shop.MTPROTO_ENABLED else False
    )
    whatsapp_trial = (
        await services.whatsapp.is_trial_available(tg_id) if config.shop.WHATSAPP_ENABLED else False
    )

    data = serialize_user(
        user=user,
        vpn_active=vpn_active,
        mtproto_active=mtproto_active,
        whatsapp_active=whatsapp_active,
        vpn_trial_available=vpn_trial,
        mtproto_trial_available=mtproto_trial,
        whatsapp_trial_available=whatsapp_trial,
    )
    data["features"] = {
        "mtproto_enabled": config.shop.MTPROTO_ENABLED,
        "whatsapp_enabled": config.shop.WHATSAPP_ENABLED,
        "stars_enabled": config.shop.PAYMENT_STARS_ENABLED,
    }

    return web.json_response(data)


async def handle_plans(request: Request) -> Response:
    """GET /api/v1/plans — VPN plans (Stars pricing)."""
    services = _services(request)
    plans = services.plan.get_all_plans()
    durations = services.plan.get_durations()
    return web.json_response({"plans": serialize_plans(plans, durations)})


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

    client_data = await services.vpn.get_client_data(user)
    key = await services.vpn.get_key(user)

    return web.json_response(serialize_vpn_subscription(client_data, key))


async def handle_subscription_mtproto(request: Request) -> Response:
    """GET /api/v1/subscription/mtproto — MTProto subscription."""
    tg_id = request["tg_id"]
    config = _config(request)
    services = _services(request)

    if not config.shop.MTPROTO_ENABLED:
        return web.json_response({"error": "MTProto is not enabled"}, status=404)

    sub = await services.mtproto.get_subscription(tg_id)
    link = await services.mtproto.get_link(tg_id) if sub else None

    return web.json_response(serialize_mtproto_subscription(sub, link))


async def handle_subscription_whatsapp(request: Request) -> Response:
    """GET /api/v1/subscription/whatsapp — WhatsApp subscription."""
    tg_id = request["tg_id"]
    config = _config(request)
    services = _services(request)

    if not config.shop.WHATSAPP_ENABLED:
        return web.json_response({"error": "WhatsApp is not enabled"}, status=404)

    sub = await services.whatsapp.get_subscription(tg_id)

    return web.json_response(
        serialize_whatsapp_subscription(sub, config.shop.WHATSAPP_HOST)
    )


async def handle_payment_invoice(request: Request) -> Response:
    """POST /api/v1/payment/invoice — Create Stars invoice link.

    Body: {"product": "vpn|mtproto|whatsapp", "devices": 3, "duration": 30, "is_extend": false}
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

    if not duration or not isinstance(duration, int) or duration <= 0:
        return web.json_response({"error": "Invalid duration"}, status=400)

    # Determine price and create invoice
    if product == "vpn":
        plan = services.plan.get_plan(devices)
        if not plan:
            return web.json_response({"error": "Plan not found"}, status=404)
        try:
            price = plan.get_price(Currency.XTR, duration)
        except (KeyError, ValueError):
            return web.json_response({"error": "Invalid duration for this plan"}, status=400)
        amount = int(price)
        title = f"VPN {devices} dev / {duration} days"
        description = f"VPN subscription: {devices} devices for {duration} days"
        product_type = "vpn"

    elif product == "mtproto":
        if not config.shop.MTPROTO_ENABLED:
            return web.json_response({"error": "MTProto is not enabled"}, status=404)
        amount = services.mtproto.get_price_stars(duration)
        if amount is None:
            return web.json_response({"error": "Invalid duration"}, status=400)
        devices = 1
        title = f"MTProto Proxy / {duration} days"
        description = f"MTProto proxy subscription for {duration} days"
        product_type = "mtproto"

    elif product == "whatsapp":
        if not config.shop.WHATSAPP_ENABLED:
            return web.json_response({"error": "WhatsApp is not enabled"}, status=404)
        amount = services.whatsapp.get_price_stars(duration)
        if amount is None:
            return web.json_response({"error": "Invalid duration"}, status=400)
        devices = 1
        title = f"WhatsApp Proxy / {duration} days"
        description = f"WhatsApp proxy subscription for {duration} days"
        product_type = "whatsapp"

    else:
        return web.json_response({"error": "Invalid product type"}, status=400)

    # Build SubscriptionData payload (same as bot flow)
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

    prices = [LabeledPrice(label=Currency.XTR.code, amount=amount)]
    try:
        invoice_url = await bot.create_invoice_link(
            title=title,
            description=description,
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


def register_routes(app: Application) -> None:
    """Register all API v1 routes."""
    app.router.add_get("/api/v1/me", handle_me)
    app.router.add_get("/api/v1/plans", handle_plans)
    app.router.add_get("/api/v1/plans/mtproto", handle_plans_mtproto)
    app.router.add_get("/api/v1/plans/whatsapp", handle_plans_whatsapp)
    app.router.add_get("/api/v1/subscription", handle_subscription_vpn)
    app.router.add_get("/api/v1/subscription/mtproto", handle_subscription_mtproto)
    app.router.add_get("/api/v1/subscription/whatsapp", handle_subscription_whatsapp)
    app.router.add_post("/api/v1/payment/invoice", handle_payment_invoice)
    app.router.add_post("/api/v1/trial/vpn", handle_trial_vpn)
    app.router.add_post("/api/v1/trial/mtproto", handle_trial_mtproto)
    app.router.add_post("/api/v1/trial/whatsapp", handle_trial_whatsapp)
