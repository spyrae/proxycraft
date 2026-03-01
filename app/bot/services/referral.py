from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bot.services import VPNService

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.utils.constants import ReferrerRewardLevel, ReferrerRewardType
from app.bot.utils.formatting import to_decimal
from app.config import Config
from app.db.models import Referral, ReferrerReward, Transaction, User

REFERRER_MAX_REWARD_DAYS = 365

logger = logging.getLogger(__name__)


class ReferralService:
    def __init__(
        self,
        config: Config,
        session_factory: async_sessionmaker,
        vpn_service: VPNService,
    ) -> None:
        self.config = config
        self.session_factory = session_factory
        self.vpn_service = vpn_service
        logger.info("Referral Service initialized")

    async def is_referred_trial_available(self, user: User) -> bool:
        is_first_check_ok = (
            self.config.shop.REFERRED_TRIAL_ENABLED
            and not user.server_id
            and not user.is_trial_used
        )
        if not is_first_check_ok:
            return False

        async with self.session_factory() as session:
            referral = await Referral.get_referral(session, user.tg_id)

        return referral and not referral.referred_rewarded_at

    async def reward_referred_user(self, user: User, days_count: int) -> bool:
        if not await self.is_referred_trial_available(user=user):
            logger.warning(
                f"Aborting. Tried to give referred-trial to the user {user.tg_id}, when it is unavailable."
            )
            return False

        async with self.session_factory() as session:
            referral = await Referral.get_referral_with_users(
                session=session, referred_tg_id=user.tg_id
            )

            rewarded = await Referral.set_rewarded(
                session=session, referral=referral, referred_bonus_days=days_count
            )
            if not rewarded:
                logger.warning(
                    f"Aborting. Tried to duplicate referred-trial period to a user {user.tg_id}"
                )
                return False

            logger.info(
                f"Started giving reward to referred user {referral.referred_tg_id}. Referral ID: {referral.id}"
            )
            referred_success = await self.vpn_service.process_bonus_days(
                referral.referred,
                duration=self.config.shop.REFERRED_TRIAL_PERIOD,
                devices=self.config.shop.BONUS_DEVICES_COUNT,
            )

            if referred_success:
                logger.info(
                    f"Referred-trial has been successfully processed for referral ID {referral.id}"
                )
                return True

            logger.warning(
                f"Failed while giving referred-trial {referral.id}. Rolling back Referral.referred_rewarded_at."
            )
            await Referral.rollback_rewarded(
                session=session,
                referral=referral,
            )

            return False

    def _apply_reward_cap(
        self,
        current_total: Decimal,
        reward_amount: int | Decimal,
    ) -> int:
        remaining = REFERRER_MAX_REWARD_DAYS - int(current_total)
        if remaining <= 0:
            return 0
        return min(int(reward_amount), remaining)

    async def add_referrers_rewards_on_payment(
        self, referred_tg_id: int, payment_amount: float, payment_id: str
    ) -> bool:
        if not self.config.shop.REFERRER_REWARD_ENABLED:
            logger.warning(
                f"Aborting. Tried to assign referrers payment reward for user {referred_tg_id}, when it is disabled."
            )
            return False

        async with self.session_factory() as session:
            # Only reward on the referred user's first completed payment
            completed_count = await Transaction.get_completed_count(session, referred_tg_id)
            if completed_count > 1:
                logger.info(
                    f"Skipping referrer reward for user {referred_tg_id}: "
                    f"not a first payment (completed={completed_count})."
                )
                return False

            referral = await Referral.get_referral_with_users(session, referred_tg_id)
            if not referral:
                logger.warning(f"No referral found for user {referred_tg_id} on payment event.")
                return False
            referrer_tg_id = referral.referrer_tg_id

            mode = self.config.shop.REFERRER_REWARD_TYPE
            reward_type = ReferrerRewardType.from_str(mode)

            if mode == ReferrerRewardType.DAYS.value:
                first_level_reward_amount = self.config.shop.REFERRER_LEVEL_ONE_PERIOD
                second_level_reward_amount = self.config.shop.REFERRER_LEVEL_TWO_PERIOD
            elif mode == ReferrerRewardType.MONEY.value:
                payment_amount = to_decimal(payment_amount)
                first_level_rate = Decimal(self.config.shop.REFERRER_LEVEL_ONE_RATE) / Decimal(100)
                second_level_rate = Decimal(self.config.shop.REFERRER_LEVEL_TWO_RATE) / Decimal(100)

                first_level_reward_amount = to_decimal(payment_amount * first_level_rate)
                second_level_reward_amount = to_decimal(payment_amount * second_level_rate)

            rewards_created = []

            # Level 1 referrer reward with 365-day cap
            if referrer_tg_id and first_level_reward_amount > 0:
                if reward_type == ReferrerRewardType.DAYS:
                    referrer_total = await ReferrerReward.get_total_rewards_sum(
                        session=session, tg_id=referrer_tg_id, reward_type=reward_type,
                    )
                    first_level_reward_amount = self._apply_reward_cap(
                        referrer_total, first_level_reward_amount,
                    )

                if first_level_reward_amount > 0:
                    reward = await ReferrerReward.create_referrer_reward(
                        session=session,
                        user_tg_id=referrer_tg_id,
                        reward_type=reward_type,
                        amount=first_level_reward_amount,
                        reward_level=ReferrerRewardLevel.FIRST_LEVEL,
                        payment_id=payment_id,
                    )
                    rewards_created.append(reward)
                else:
                    logger.info(
                        f"Referrer {referrer_tg_id} reached {REFERRER_MAX_REWARD_DAYS}-day cap. "
                        f"Level 1 reward skipped."
                    )

            # Level 2 referrer reward with 365-day cap
            second_level_referral = await Referral.get_referral(session, referrer_tg_id)
            if (
                second_level_reward_amount > 0
                and second_level_referral
                and second_level_referral.referrer_tg_id
            ):
                second_referrer_tg_id = second_level_referral.referrer_tg_id

                if reward_type == ReferrerRewardType.DAYS:
                    second_referrer_total = await ReferrerReward.get_total_rewards_sum(
                        session=session, tg_id=second_referrer_tg_id, reward_type=reward_type,
                    )
                    second_level_reward_amount = self._apply_reward_cap(
                        second_referrer_total, second_level_reward_amount,
                    )

                if second_level_reward_amount > 0:
                    reward = await ReferrerReward.create_referrer_reward(
                        session=session,
                        user_tg_id=second_referrer_tg_id,
                        reward_type=reward_type,
                        amount=second_level_reward_amount,
                        reward_level=ReferrerRewardLevel.SECOND_LEVEL,
                        payment_id=payment_id,
                    )
                    rewards_created.append(reward)
                else:
                    logger.info(
                        f"Second-level referrer {second_referrer_tg_id} reached "
                        f"{REFERRER_MAX_REWARD_DAYS}-day cap. Level 2 reward skipped."
                    )

            # Auto +N days bonus for the referred user on first payment
            referred_trial_period = self.config.shop.REFERRED_TRIAL_PERIOD
            if referred_trial_period > 0:
                reward = await ReferrerReward.create_referrer_reward(
                    session=session,
                    user_tg_id=referred_tg_id,
                    reward_type=ReferrerRewardType.DAYS,
                    amount=referred_trial_period,
                    reward_level=None,
                    payment_id=payment_id,
                )
                if reward:
                    rewards_created.append(reward)
                    logger.info(
                        f"Created +{referred_trial_period} days bonus for referred user {referred_tg_id}."
                    )

            return bool(rewards_created)

    async def process_referrer_rewards_after_payment(self, reward: ReferrerReward) -> bool:
        if reward.rewarded_at:
            logger.info(
                f"ReferrerReward {reward.id} (tg_id: {reward.user_tg_id}) was already given earlier."
            )
            return False

        async with self.session_factory() as session:
            if reward.reward_type == ReferrerRewardType.DAYS:
                days = int(reward.amount)
                user = await User.get(session=session, tg_id=reward.user_tg_id)
                if not user:
                    return False

                success = await self.vpn_service.process_bonus_days(
                    user=user, duration=days, devices=self.config.shop.BONUS_DEVICES_COUNT
                )
                if not success:
                    logger.error(
                        f"Failed to give {days} days reward to a referrer user {reward.user_tg_id}"
                    )
                    return False

                logger.info(f"Gave {days} days to a referrer user {reward.user_tg_id}")

            elif reward.reward_type == ReferrerRewardType.MONEY:
                # TODO: add balance processing
                logger.critical(
                    f"Tried to give money {reward.amount} reward to a referrer user {reward.user_tg_id}"
                )

            else:
                logger.warning(
                    f"Failed to give referrer reward. Unknown reward type: {reward.reward_type}"
                )
                return False

            await ReferrerReward.mark_reward_as_given(session=session, reward=reward)

            logger.info(
                f"ReferrerReward {reward.id} (tg_id: {reward.user_tg_id}) successfully rewarded."
            )
            return True
