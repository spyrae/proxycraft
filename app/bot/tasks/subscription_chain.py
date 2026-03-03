import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram.utils.i18n import I18n
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.models import ClientData
from app.bot.routers.subscription.keyboard import renew_keyboard
from app.bot.services import NotificationService, VPNService
from app.db.models import SubscriptionEvent, User

logger = logging.getLogger(__name__)

# Stage definitions: (stage_name, i18n_key, include_keyboard, bonus_days)
PRE_EXPIRY_STAGES = [
    ("t_5d", "task:message:expiry_5d", False, 0),
    ("t_3d", "task:message:expiry_3d", True, 0),
    ("t_1d", "task:message:expiry_1d", True, 0),
    ("t_0", "task:message:expiry_0", True, 0),
]

POST_EXPIRY_STAGES = [
    ("t_p3d", "task:message:winback_3d", True, 5),
    ("t_p14d", "task:message:winback_14d", True, 15),
]

# Window definitions: (stage, min_timedelta, max_timedelta)
# For pre-expiry: time_left = expiry - now (positive means not expired yet)
PRE_EXPIRY_WINDOWS = {
    "t_5d": (timedelta(days=4), timedelta(days=5, hours=1)),
    "t_3d": (timedelta(days=2), timedelta(days=3, hours=1)),
    "t_1d": (timedelta(0), timedelta(days=1, hours=1)),
    "t_0": (timedelta(hours=-1), timedelta(0)),
}

# For post-expiry: since_expiry = now - expiry (positive means time since expiry)
POST_EXPIRY_WINDOWS = {
    "t_p3d": (timedelta(days=3), timedelta(days=3, hours=1)),
    "t_p14d": (timedelta(days=14), timedelta(days=14, hours=1)),
}


def _get_pre_expiry_stage(time_left: timedelta) -> str | None:
    """Determine which pre-expiry stage the user falls into."""
    for stage, (min_td, max_td) in PRE_EXPIRY_WINDOWS.items():
        if min_td < time_left <= max_td:
            return stage
    return None


def _get_post_expiry_stage(since_expiry: timedelta) -> str | None:
    """Determine which post-expiry stage the user falls into."""
    for stage, (min_td, max_td) in POST_EXPIRY_WINDOWS.items():
        if min_td <= since_expiry < max_td:
            return stage
    return None


async def process_subscription_chain(
    session_factory: async_sessionmaker,
    i18n: I18n,
    vpn_service: VPNService,
    notification_service: NotificationService,
) -> None:
    """Main subscription notification chain task."""
    session: AsyncSession
    async with session_factory() as session:
        users = await User.get_all(session=session)

    logger.info(
        f"[subscription_chain] Starting check for {len(users)} users."
    )

    # Batch fetch all clients (1 API call per server)
    all_clients = await vpn_service.get_all_clients_data()
    now = datetime.now(timezone.utc)
    notifications_sent = 0

    for user in users:
        client_data = all_clients.get(str(user.tg_id))

        # Skip if no client data or unlimited subscription
        if not client_data or client_data._expiry_time == -1:
            continue

        expiry_ms = client_data._expiry_time
        expiry_datetime = datetime.fromtimestamp(expiry_ms / 1000, timezone.utc)
        time_left = expiry_datetime - now

        # Try pre-expiry stages
        pre_stage = _get_pre_expiry_stage(time_left)
        if pre_stage:
            sent = await _handle_pre_expiry(
                session_factory=session_factory,
                user=user,
                stage=pre_stage,
                expiry_ms=expiry_ms,
                i18n=i18n,
                vpn_service=vpn_service,
                notification_service=notification_service,
            )
            if sent:
                notifications_sent += 1
                await asyncio.sleep(0.05)  # Rate limiting: 20 msg/sec
            continue

        # Try post-expiry stages (only if subscription already expired)
        if time_left.total_seconds() < 0:
            since_expiry = now - expiry_datetime
            post_stage = _get_post_expiry_stage(since_expiry)
            if post_stage:
                sent = await _handle_post_expiry(
                    session_factory=session_factory,
                    user=user,
                    stage=post_stage,
                    expiry_ms=expiry_ms,
                    i18n=i18n,
                    notification_service=notification_service,
                )
                if sent:
                    notifications_sent += 1
                    await asyncio.sleep(0.05)

    logger.info(
        f"[subscription_chain] Check finished. Sent {notifications_sent} notifications."
    )


async def _handle_pre_expiry(
    session_factory: async_sessionmaker,
    user: User,
    stage: str,
    expiry_ms: int,
    i18n: I18n,
    vpn_service: VPNService,
    notification_service: NotificationService,
) -> bool:
    """Handle pre-expiry notification (T-5, T-3, T-1, T+0)."""
    async with session_factory() as session:
        # Deduplicate via DB UNIQUE constraint
        if await SubscriptionEvent.exists(session, user.tg_id, expiry_ms, stage):
            return False

    # Find stage config
    stage_config = next((s for s in PRE_EXPIRY_STAGES if s[0] == stage), None)
    if not stage_config:
        return False

    _, i18n_key, include_keyboard, _ = stage_config

    # Send notification
    text = i18n.gettext(i18n_key, locale=user.language_code)
    reply_markup = renew_keyboard() if include_keyboard else None

    await notification_service.notify_by_id(
        chat_id=user.tg_id,
        text=text,
        reply_markup=reply_markup,
    )

    # T+0: also disable client
    if stage == "t_0":
        disabled = await vpn_service.disable_client(user)
        if disabled:
            logger.info(f"[subscription_chain] Client {user.tg_id} disabled at T+0.")
        else:
            logger.warning(f"[subscription_chain] Failed to disable client {user.tg_id} at T+0.")

    # Record event
    async with session_factory() as session:
        await SubscriptionEvent.create(session, user.tg_id, stage, expiry_ms)

    logger.info(f"[subscription_chain] Sent {stage} notification to user {user.tg_id}.")
    return True


async def _handle_post_expiry(
    session_factory: async_sessionmaker,
    user: User,
    stage: str,
    expiry_ms: int,
    i18n: I18n,
    notification_service: NotificationService,
) -> bool:
    """Handle post-expiry notification (T+3, T+14) — win-back messages."""
    async with session_factory() as session:
        # Check that T+0 event exists for this expiry cycle
        t0_event = await SubscriptionEvent.get_latest_by_stage(session, user.tg_id, "t_0")
        if not t0_event:
            return False

        # Check that user hasn't renewed (expiry_time should still match)
        if t0_event.expiry_time != expiry_ms:
            # User renewed — new expiry_time differs from when T+0 was sent
            return False

        # Deduplicate
        if await SubscriptionEvent.exists(session, user.tg_id, expiry_ms, stage):
            return False

    # Find stage config
    stage_config = next((s for s in POST_EXPIRY_STAGES if s[0] == stage), None)
    if not stage_config:
        return False

    _, i18n_key, include_keyboard, _ = stage_config

    # Send notification
    text = i18n.gettext(i18n_key, locale=user.language_code)
    reply_markup = renew_keyboard() if include_keyboard else None

    await notification_service.notify_by_id(
        chat_id=user.tg_id,
        text=text,
        reply_markup=reply_markup,
    )

    # Record event
    async with session_factory() as session:
        await SubscriptionEvent.create(session, user.tg_id, stage, expiry_ms)

    logger.info(f"[subscription_chain] Sent {stage} win-back notification to user {user.tg_id}.")
    return True


def start_scheduler(
    session_factory: async_sessionmaker,
    i18n: I18n,
    vpn_service: VPNService,
    notification_service: NotificationService,
) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        process_subscription_chain,
        "interval",
        hours=1,
        args=[session_factory, i18n, vpn_service, notification_service],
        next_run_time=datetime.now(tz=timezone.utc),
    )
    scheduler.start()
    logger.info("[subscription_chain] Scheduler started (interval: 1 hour).")
