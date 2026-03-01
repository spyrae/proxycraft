import logging
import uuid

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
    serialize_mtproto_plans,
    serialize_mtproto_subscription,
    serialize_operators,
    serialize_vpn_products,
    serialize_user,
    serialize_vpn_subscription,
    serialize_whatsapp_plans,
    serialize_whatsapp_subscription,
)
from app.bot.filters.is_admin import IsAdmin
from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.utils.constants import Currency, TransactionStatus
from app.bot.utils.navigation import NavSubscription, NavMTProto, NavWhatsApp
from app.db.models import Server, Transaction, User

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
    data["is_admin"] = await IsAdmin()(user_id=tg_id)

    return web.json_response(data)


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

    catalog = services.product_catalog

    # Determine price and create invoice
    if product == "vpn":
        vpn_product = catalog.get_vpn_product_by_devices(devices)
        if not vpn_product:
            return web.json_response({"error": "Plan not found"}, status=404)
        price = catalog.get_price(vpn_product.slug, Currency.XTR.code, duration)
        if price is None:
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

    elif product.startswith("bundle_"):
        if not (config.shop.MTPROTO_ENABLED and config.shop.WHATSAPP_ENABLED):
            return web.json_response({"error": "Bundles require MTProto and WhatsApp"}, status=404)
        bundle_product = catalog.get_product(product)
        if not bundle_product or not bundle_product.is_bundle:
            return web.json_response({"error": "Invalid bundle"}, status=400)
        amount = catalog.calculate_price_stars(product, duration)
        devices = 1
        title = f"{bundle_product.name} / {duration} days"
        description = f"{bundle_product.description} for {duration} days"
        product_type = product

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


def register_routes(app: Application) -> None:
    """Register all API v1 routes."""
    app.router.add_get("/api/v1/me", handle_me)
    app.router.add_get("/api/v1/operators", handle_operators)
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
    app.router.add_get("/api/v1/plans/bundles", handle_plans_bundles)
    app.router.add_post("/api/v1/trial/bundle", handle_trial_bundle)

    # Admin endpoints
    app.router.add_post("/api/v1/admin/auth", handle_admin_auth)
    app.router.add_get("/api/v1/admin/stats", handle_admin_stats)
    app.router.add_get("/api/v1/admin/users", handle_admin_users)
    app.router.add_get("/api/v1/admin/users/{tg_id}", handle_admin_user_detail)
    app.router.add_get("/api/v1/admin/servers", handle_admin_servers)
