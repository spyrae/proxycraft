import logging
from datetime import datetime, timedelta, timezone

from aiogram.utils.i18n import I18n
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio.client import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.services import NotificationService, VPNService
from app.bot.services.product_catalog import ProductCatalog
from app.bot.utils.constants import Currency
from app.db.models import BalanceLog, User

logger = logging.getLogger(__name__)

RENEWAL_DURATION = 30  # days


async def process_auto_renewals(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    vpn_service: VPNService,
    notification_service: NotificationService,
    product_catalog: ProductCatalog,
) -> None:
    """Check users with auto_renew=True and renew if expiring within 24h."""
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(User.auto_renew == True)  # noqa: E712
        )
        users = result.scalars().all()

    logger.info(f"[auto_renew] Checking {len(users)} users with auto_renew=True.")

    all_clients = await vpn_service.get_all_clients_data()
    now = datetime.now(timezone.utc)
    renewed = 0
    insufficient = 0

    for user in users:
        client_data = all_clients.get(str(user.tg_id))

        # Skip if no subscription or unlimited
        if not client_data or client_data._expiry_time <= 0:
            continue

        expiry_datetime = datetime.fromtimestamp(
            client_data._expiry_time / 1000, timezone.utc
        )
        time_left = expiry_datetime - now

        # Only renew if within 24h window (and not already expired)
        if not (timedelta(0) < time_left <= timedelta(hours=24)):
            continue

        # Calculate price for current device count and 30 days
        max_devices = client_data._max_devices if client_data._max_devices > 0 else 1
        vpn_product = product_catalog.get_vpn_product_by_devices(max_devices)
        if not vpn_product:
            logger.warning(
                f"[auto_renew] No product found for {max_devices} devices, user {user.tg_id}"
            )
            continue

        price_rub = product_catalog.get_price(vpn_product.slug, Currency.RUB.code, RENEWAL_DURATION)
        if price_rub is None:
            logger.warning(
                f"[auto_renew] No price for {vpn_product.slug}/{RENEWAL_DURATION}d, user {user.tg_id}"
            )
            continue

        price_kopecks = int(round(float(price_rub) * 100))

        if user.balance >= price_kopecks:
            # Deduct and extend
            async with session_factory() as session:
                # Re-fetch for atomicity
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
                f"[auto_renew] Renewed user {user.tg_id}: "
                f"{max_devices} dev, {RENEWAL_DURATION}d, {price_kopecks/100}₽"
            )
        else:
            # Insufficient balance — notify once per 24h
            dedup_key = f"auto_renew:insufficient:{user.tg_id}"
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
                f"[auto_renew] Insufficient balance for user {user.tg_id}: "
                f"has {user.balance/100}₽, needs {price_kopecks/100}₽"
            )

    logger.info(
        f"[auto_renew] Finished. Renewed: {renewed}, Insufficient: {insufficient}."
    )


def start_scheduler(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    vpn_service: VPNService,
    notification_service: NotificationService,
    product_catalog: ProductCatalog,
) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        process_auto_renewals,
        "interval",
        minutes=30,
        args=[session_factory, redis, i18n, vpn_service, notification_service, product_catalog],
        next_run_time=datetime.now(tz=timezone.utc),
    )
    scheduler.start()
    logger.info("[auto_renew] Scheduler started (interval: 30 min).")
