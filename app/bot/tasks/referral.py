import logging
from datetime import datetime

from aiogram import Bot
from aiogram.utils.i18n import I18n
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.services import ReferralService
from app.bot.utils.constants import ReferrerRewardType
from app.bot.utils.formatting import format_subscription_period
from app.db.models import ReferrerReward, User

logger = logging.getLogger(__name__)


async def reward_pending_referrals_after_payment(
    session_factory: async_sessionmaker,
    referral_service: ReferralService,
    bot: Bot,
    i18n: I18n,
) -> None:
    session: AsyncSession
    async with session_factory() as session:
        stmt = select(ReferrerReward).where(ReferrerReward.rewarded_at.is_(None))
        result = await session.execute(stmt)
        pending_rewards = result.scalars().all()

        logger.info(f"[Background check] Found {len(pending_rewards)} not proceed rewards.")

        for reward in pending_rewards:
            success = await referral_service.process_referrer_rewards_after_payment(reward=reward)
            if not success:
                logger.warning(
                    f"[Background check] Reward {reward.id} was NOT proceed successfully."
                )
                continue

            # Send notification to the rewarded user
            try:
                user = await User.get(session=session, tg_id=reward.user_tg_id)
                locale = user.language_code if user else "en"

                if reward.reward_type == ReferrerRewardType.DAYS:
                    duration = format_subscription_period(int(reward.amount))
                    text = i18n.gettext(
                        "referral:ntf:referrer_reward_received",
                        locale=locale,
                    ).format(duration=duration)
                elif reward.reward_type == ReferrerRewardType.MONEY:
                    text = i18n.gettext(
                        "referral:ntf:referrer_balance_reward_received",
                        locale=locale,
                    ).format(amount=int(reward.amount))
                else:
                    text = None

                if text:
                    await bot.send_message(chat_id=reward.user_tg_id, text=text)
                    logger.info(
                        f"[Background check] Sent reward notification to user {reward.user_tg_id}."
                    )
            except Exception as e:
                logger.warning(
                    f"[Background check] Failed to notify user {reward.user_tg_id}: {e}"
                )

        logger.info("[Background check] Referrer rewards check finished.")


def start_scheduler(
    session_factory: async_sessionmaker,
    referral_service: ReferralService,
    bot: Bot,
    i18n: I18n,
) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        reward_pending_referrals_after_payment,
        "interval",
        minutes=15,
        args=[session_factory, referral_service, bot, i18n],
        next_run_time=datetime.now(),
    )
    scheduler.start()
