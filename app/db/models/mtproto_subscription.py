import logging
from datetime import datetime
from typing import Any, Self

from sqlalchemy import ForeignKey, String, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from . import Base

logger = logging.getLogger(__name__)


class MTProtoSubscription(Base):
    """
    Represents an MTProto proxy subscription in the database.

    Attributes:
        id (int): Unique primary key.
        user_tg_id (int): Telegram user ID (unique, FK to users.tg_id).
        secret (str): 32-char hex secret for mtprotoproxy.
        activated_at (datetime): When the subscription was activated.
        expires_at (datetime): When the subscription expires.
        is_active (bool): Whether the subscription is currently active.
        is_trial_used (bool): Whether the user has used the free trial.
    """

    __tablename__ = "proxycraft_mtproto_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_tg_id: Mapped[int] = mapped_column(
        ForeignKey("proxycraft_users.tg_id", ondelete="CASCADE"), unique=True, nullable=False
    )
    secret: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_trial_used: Mapped[bool] = mapped_column(default=False, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)

    def __repr__(self) -> str:
        return (
            f"<MTProtoSubscription(id={self.id}, user_tg_id={self.user_tg_id}, "
            f"secret='{self.secret[:8]}...', expires_at={self.expires_at}, "
            f"is_active={self.is_active})>"
        )

    @classmethod
    async def get_by_user(cls, session: AsyncSession, user_tg_id: int) -> Self | None:
        query = await session.execute(
            select(MTProtoSubscription).where(MTProtoSubscription.user_tg_id == user_tg_id)
        )
        return query.scalar_one_or_none()

    @classmethod
    async def create(
        cls, session: AsyncSession, user_tg_id: int, secret: str, expires_at: datetime, **kwargs: Any
    ) -> Self | None:
        existing = await cls.get_by_user(session=session, user_tg_id=user_tg_id)
        if existing:
            logger.warning(f"MTProto subscription already exists for user {user_tg_id}")
            return None

        sub = MTProtoSubscription(
            user_tg_id=user_tg_id,
            secret=secret,
            expires_at=expires_at,
            **kwargs,
        )
        session.add(sub)
        try:
            await session.commit()
            logger.info(f"MTProto subscription created for user {user_tg_id}")
            return sub
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Error creating MTProto subscription for user {user_tg_id}: {e}")
            return None

    @classmethod
    async def update_expiry(
        cls, session: AsyncSession, user_tg_id: int, expires_at: datetime
    ) -> Self | None:
        sub = await cls.get_by_user(session=session, user_tg_id=user_tg_id)
        if not sub:
            logger.warning(f"MTProto subscription not found for user {user_tg_id}")
            return None

        await session.execute(
            update(MTProtoSubscription)
            .where(MTProtoSubscription.user_tg_id == user_tg_id)
            .values(expires_at=expires_at, is_active=True)
        )
        await session.commit()
        logger.info(f"MTProto subscription extended for user {user_tg_id}")
        return sub

    @classmethod
    async def deactivate(cls, session: AsyncSession, user_tg_id: int) -> bool:
        sub = await cls.get_by_user(session=session, user_tg_id=user_tg_id)
        if not sub:
            return False

        await session.execute(
            update(MTProtoSubscription)
            .where(MTProtoSubscription.user_tg_id == user_tg_id)
            .values(is_active=False)
        )
        await session.commit()
        logger.info(f"MTProto subscription deactivated for user {user_tg_id}")
        return True

    @classmethod
    async def get_all_active(cls, session: AsyncSession) -> list[Self]:
        query = await session.execute(
            select(MTProtoSubscription).where(MTProtoSubscription.is_active == True)
        )
        return list(query.scalars().all())

    @classmethod
    async def get_expired_active(cls, session: AsyncSession) -> list[Self]:
        now = datetime.utcnow()
        query = await session.execute(
            select(MTProtoSubscription).where(
                MTProtoSubscription.is_active == True,
                MTProtoSubscription.expires_at <= now,
            )
        )
        return list(query.scalars().all())

    @classmethod
    async def cancel(cls, session: AsyncSession, user_tg_id: int) -> Self | None:
        """Mark subscription as cancelled (stops auto-renew; stays active until expires_at)."""
        sub = await cls.get_by_user(session=session, user_tg_id=user_tg_id)
        if not sub or sub.cancelled_at is not None:
            return sub

        await session.execute(
            update(MTProtoSubscription)
            .where(MTProtoSubscription.user_tg_id == user_tg_id)
            .values(cancelled_at=datetime.utcnow())
        )
        await session.commit()
        await session.refresh(sub)
        logger.info(f"MTProto subscription cancelled for user {user_tg_id}")
        return sub

    @classmethod
    async def mark_trial_used(cls, session: AsyncSession, user_tg_id: int) -> bool:
        sub = await cls.get_by_user(session=session, user_tg_id=user_tg_id)
        if not sub:
            return False

        await session.execute(
            update(MTProtoSubscription)
            .where(MTProtoSubscription.user_tg_id == user_tg_id)
            .values(is_trial_used=True)
        )
        await session.commit()
        return True
