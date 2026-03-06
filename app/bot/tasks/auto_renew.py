import logging
from datetime import datetime, timedelta, timezone

from aiogram.utils.i18n import I18n
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio.client import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.services import MTProtoService, NotificationService, VPNService, WhatsAppService
from app.bot.services.product_catalog import ProductCatalog
from app.bot.utils.constants import Currency
from app.db.models import BalanceLog, MTProtoSubscription, User, WhatsAppSubscription

logger = logging.getLogger(__name__)

RENEWAL_DURATION = 30  # days


async def process_auto_renewals(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    vpn_service: VPNService,
    mtproto_service: MTProtoService,
    whatsapp_service: WhatsAppService,
    notification_service: NotificationService,
    product_catalog: ProductCatalog,
) -> None:
    """Check all subscriptions and auto-renew if expiring within 24h and not cancelled."""
    await _renew_vpn(session_factory, redis, i18n, vpn_service, notification_service, product_catalog)
    await _renew_mtproto(session_factory, redis, i18n, mtproto_service, notification_service)
    await _renew_whatsapp(session_factory, redis, i18n, whatsapp_service, notification_service)


async def _renew_vpn(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    vpn_service: VPNService,
    notification_service: NotificationService,
    product_catalog: ProductCatalog,
) -> None:
    """Auto-renew VPN subscriptions expiring within 24h (auto_renew=True, not cancelled)."""
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(
                User.auto_renew == True,  # noqa: E712
                User.vpn_cancelled_at == None,  # noqa: E711
            )
        )
        users = result.scalars().all()

    logger.info(f"[auto_renew/vpn] Checking {len(users)} eligible users.")

    all_clients = await vpn_service.get_all_clients_data()
    now = datetime.now(timezone.utc)
    renewed = 0
    insufficient = 0

    for user in users:
        client_data = all_clients.get(str(user.tg_id))

        if not client_data or client_data._expiry_time <= 0:
            continue

        expiry_datetime = datetime.fromtimestamp(
            client_data._expiry_time / 1000, timezone.utc
        )
        time_left = expiry_datetime - now

        if not (timedelta(0) < time_left <= timedelta(hours=24)):
            continue

        max_devices = client_data._max_devices if client_data._max_devices > 0 else 1
        vpn_product = product_catalog.get_vpn_product_by_devices(max_devices)
        if not vpn_product:
            logger.warning(
                f"[auto_renew/vpn] No product for {max_devices} devices, user {user.tg_id}"
            )
            continue

        price_rub = product_catalog.get_price(vpn_product.slug, Currency.RUB.code, RENEWAL_DURATION)
        if price_rub is None:
            logger.warning(
                f"[auto_renew/vpn] No price for {vpn_product.slug}/{RENEWAL_DURATION}d, user {user.tg_id}"
            )
            continue

        price_kopecks = int(round(float(price_rub) * 100))

        if user.balance >= price_kopecks:
            async with session_factory() as session:
                db_user = await User.get(session=session, tg_id=user.tg_id)
                if db_user.balance < price_kopecks:
                    continue

                await User.update(
                    session=session,
                    tg_id=user.tg_id,
                    balance=db_user.balance - price_kopecks,
                )
                await BalanceLog.create(
                    session=session,
                    tg_id=user.tg_id,
                    amount=-price_kopecks,
                    type="auto_renew",
                    description=f"Auto-renew VPN {max_devices} dev / {RENEWAL_DURATION}d",
                )

            await vpn_service.extend_subscription(
                user=user, devices=max_devices, duration=RENEWAL_DURATION
            )

            locale = user.language_code or "ru"
            text = i18n.gettext("task:message:auto_renew_success", locale=locale).format(
                price=price_kopecks // 100,
                balance=(user.balance - price_kopecks) // 100,
            )
            await notification_service.notify_by_id(chat_id=user.tg_id, text=text)
            renewed += 1
            logger.info(
                f"[auto_renew/vpn] Renewed user {user.tg_id}: "
                f"{max_devices} dev, {RENEWAL_DURATION}d, {price_kopecks/100}₽"
            )
        else:
            dedup_key = f"auto_renew:insufficient:vpn:{user.tg_id}"
            if await redis.get(dedup_key):
                continue

            locale = user.language_code or "ru"
            text = i18n.gettext("task:message:auto_renew_insufficient", locale=locale).format(
                balance=user.balance // 100,
                price=price_kopecks // 100,
            )
            await notification_service.notify_by_id(chat_id=user.tg_id, text=text)
            await redis.set(dedup_key, "1", ex=timedelta(hours=24))
            insufficient += 1
            logger.info(
                f"[auto_renew/vpn] Insufficient for user {user.tg_id}: "
                f"has {user.balance/100}₽, needs {price_kopecks/100}₽"
            )

    logger.info(f"[auto_renew/vpn] Done. Renewed: {renewed}, Insufficient: {insufficient}.")


async def _renew_mtproto(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    mtproto_service: MTProtoService,
    notification_service: NotificationService,
) -> None:
    """Auto-renew MTProto subscriptions expiring within 24h (not cancelled)."""
    now = datetime.utcnow()
    threshold = now + timedelta(hours=24)

    async with session_factory() as session:
        result = await session.execute(
            select(MTProtoSubscription).where(
                MTProtoSubscription.is_active == True,  # noqa: E712
                MTProtoSubscription.cancelled_at == None,  # noqa: E711
                MTProtoSubscription.expires_at > now,
                MTProtoSubscription.expires_at <= threshold,
            )
        )
        subs = result.scalars().all()

    logger.info(f"[auto_renew/mtproto] Checking {len(subs)} expiring subscriptions.")
    renewed = 0
    insufficient = 0

    for sub in subs:
        price_rub = mtproto_service.get_price(RENEWAL_DURATION)
        if price_rub is None:
            logger.warning(f"[auto_renew/mtproto] No price for {RENEWAL_DURATION}d, user {sub.user_tg_id}")
            continue

        price_kopecks = price_rub * 100

        async with session_factory() as session:
            user = await User.get(session=session, tg_id=sub.user_tg_id)

        if not user:
            continue

        if user.balance >= price_kopecks:
            async with session_factory() as session:
                db_user = await User.get(session=session, tg_id=sub.user_tg_id)
                if db_user.balance < price_kopecks:
                    continue

                await User.update(
                    session=session,
                    tg_id=sub.user_tg_id,
                    balance=db_user.balance - price_kopecks,
                )
                await BalanceLog.create(
                    session=session,
                    tg_id=sub.user_tg_id,
                    amount=-price_kopecks,
                    type="auto_renew",
                    description=f"Auto-renew MTProto {RENEWAL_DURATION}d",
                )

            await mtproto_service.extend(sub.user_tg_id, RENEWAL_DURATION)

            locale = user.language_code or "ru"
            text = i18n.gettext("task:message:mtproto_renew_success", locale=locale).format(
                price=price_rub,
                balance=(db_user.balance - price_kopecks) // 100,
            )
            await notification_service.notify_by_id(chat_id=sub.user_tg_id, text=text)
            renewed += 1
            logger.info(
                f"[auto_renew/mtproto] Renewed user {sub.user_tg_id}: {RENEWAL_DURATION}d, {price_rub}₽"
            )
        else:
            dedup_key = f"auto_renew:insufficient:mtproto:{sub.user_tg_id}"
            if await redis.get(dedup_key):
                continue

            locale = user.language_code or "ru"
            text = i18n.gettext("task:message:mtproto_renew_insufficient", locale=locale).format(
                balance=user.balance // 100,
                price=price_rub,
            )
            await notification_service.notify_by_id(chat_id=sub.user_tg_id, text=text)
            await redis.set(dedup_key, "1", ex=timedelta(hours=24))
            insufficient += 1
            logger.info(
                f"[auto_renew/mtproto] Insufficient for user {sub.user_tg_id}: "
                f"has {user.balance/100}₽, needs {price_rub}₽"
            )

    logger.info(f"[auto_renew/mtproto] Done. Renewed: {renewed}, Insufficient: {insufficient}.")


async def _renew_whatsapp(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    whatsapp_service: WhatsAppService,
    notification_service: NotificationService,
) -> None:
    """Auto-renew WhatsApp subscriptions expiring within 24h (not cancelled)."""
    now = datetime.utcnow()
    threshold = now + timedelta(hours=24)

    async with session_factory() as session:
        result = await session.execute(
            select(WhatsAppSubscription).where(
                WhatsAppSubscription.is_active == True,  # noqa: E712
                WhatsAppSubscription.cancelled_at == None,  # noqa: E711
                WhatsAppSubscription.expires_at > now,
                WhatsAppSubscription.expires_at <= threshold,
            )
        )
        subs = result.scalars().all()

    logger.info(f"[auto_renew/whatsapp] Checking {len(subs)} expiring subscriptions.")
    renewed = 0
    insufficient = 0

    for sub in subs:
        price_rub = whatsapp_service.get_price(RENEWAL_DURATION)
        if price_rub is None:
            logger.warning(f"[auto_renew/whatsapp] No price for {RENEWAL_DURATION}d, user {sub.user_tg_id}")
            continue

        price_kopecks = price_rub * 100

        async with session_factory() as session:
            user = await User.get(session=session, tg_id=sub.user_tg_id)

        if not user:
            continue

        if user.balance >= price_kopecks:
            async with session_factory() as session:
                db_user = await User.get(session=session, tg_id=sub.user_tg_id)
                if db_user.balance < price_kopecks:
                    continue

                await User.update(
                    session=session,
                    tg_id=sub.user_tg_id,
                    balance=db_user.balance - price_kopecks,
                )
                await BalanceLog.create(
                    session=session,
                    tg_id=sub.user_tg_id,
                    amount=-price_kopecks,
                    type="auto_renew",
                    description=f"Auto-renew WhatsApp {RENEWAL_DURATION}d",
                )

            await whatsapp_service.extend(sub.user_tg_id, RENEWAL_DURATION)

            locale = user.language_code or "ru"
            text = i18n.gettext("task:message:whatsapp_renew_success", locale=locale).format(
                price=price_rub,
                balance=(db_user.balance - price_kopecks) // 100,
            )
            await notification_service.notify_by_id(chat_id=sub.user_tg_id, text=text)
            renewed += 1
            logger.info(
                f"[auto_renew/whatsapp] Renewed user {sub.user_tg_id}: {RENEWAL_DURATION}d, {price_rub}₽"
            )
        else:
            dedup_key = f"auto_renew:insufficient:whatsapp:{sub.user_tg_id}"
            if await redis.get(dedup_key):
                continue

            locale = user.language_code or "ru"
            text = i18n.gettext("task:message:whatsapp_renew_insufficient", locale=locale).format(
                balance=user.balance // 100,
                price=price_rub,
            )
            await notification_service.notify_by_id(chat_id=sub.user_tg_id, text=text)
            await redis.set(dedup_key, "1", ex=timedelta(hours=24))
            insufficient += 1
            logger.info(
                f"[auto_renew/whatsapp] Insufficient for user {sub.user_tg_id}: "
                f"has {user.balance/100}₽, needs {price_rub}₽"
            )

    logger.info(f"[auto_renew/whatsapp] Done. Renewed: {renewed}, Insufficient: {insufficient}.")


def start_scheduler(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    vpn_service: VPNService,
    mtproto_service: MTProtoService,
    whatsapp_service: WhatsAppService,
    notification_service: NotificationService,
    product_catalog: ProductCatalog,
) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        process_auto_renewals,
        "interval",
        minutes=30,
        args=[
            session_factory, redis, i18n,
            vpn_service, mtproto_service, whatsapp_service,
            notification_service, product_catalog,
        ],
        next_run_time=datetime.now(tz=timezone.utc),
    )
    scheduler.start()
    logger.info("[auto_renew] Scheduler started (interval: 30 min, covers VPN + MTProto + WhatsApp).")
