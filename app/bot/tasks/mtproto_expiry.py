import logging
from datetime import datetime, timedelta, timezone

from aiogram.utils.i18n import I18n
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.services import MTProtoService, NotificationService
from app.db.models import MTProtoSubscription

logger = logging.getLogger(__name__)


async def cleanup_and_notify_mtproto(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    mtproto_service: MTProtoService,
    notification_service: NotificationService,
) -> None:
    """Clean up expired MTProto subscriptions and notify users about expiring ones."""

    # 1. Notify users whose subscription expires within 24 hours
    async with session_factory() as session:
        active_subs = await MTProtoSubscription.get_all_active(session)

        now = datetime.utcnow()

        for sub in active_subs:
            user_notified_key = f"mtproto:notified:{sub.user_tg_id}"

            # Skip if already notified
            if await redis.get(user_notified_key):
                continue

            time_left = sub.expires_at - now

            # Notify if expiring within 24 hours
            if timedelta(0) < time_left <= timedelta(hours=24):
                try:
                    await notification_service.notify_by_id(
                        chat_id=sub.user_tg_id,
                        text=i18n.gettext(
                            "mtproto:message:expiring_soon",
                            locale="ru",
                        ).format(
                            expires_at=sub.expires_at.strftime("%d.%m.%Y %H:%M UTC"),
                        ),
                    )
                    await redis.set(user_notified_key, "true", ex=timedelta(hours=24))
                    logger.info(f"Sent MTProto expiry notification to user {sub.user_tg_id}")
                except Exception as e:
                    logger.error(f"Failed to notify user {sub.user_tg_id} about MTProto expiry: {e}")

    # 2. Cleanup expired subscriptions
    count = await mtproto_service.cleanup_expired()
    if count > 0:
        logger.info(f"[MTProto task] Cleaned up {count} expired subscriptions.")


def start_scheduler(
    session_factory: async_sessionmaker,
    redis: Redis,
    i18n: I18n,
    mtproto_service: MTProtoService,
    notification_service: NotificationService,
) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        cleanup_and_notify_mtproto,
        "interval",
        hours=1,
        args=[session_factory, redis, i18n, mtproto_service, notification_service],
        next_run_time=datetime.now(tz=timezone.utc),
    )
    scheduler.start()
