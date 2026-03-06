import logging
import random
from datetime import datetime
from typing import Any, Self

from sqlalchemy import ForeignKey, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from . import Base

logger = logging.getLogger(__name__)

# Port range for WhatsApp proxy
WHATSAPP_PORT_MIN = 10001
WHATSAPP_PORT_MAX = 10999


class WhatsAppSubscription(Base):
    """
    Represents a WhatsApp proxy subscription in the database.

    Each user gets a unique port on HAProxy for TCP pass-through to g.whatsapp.net.

    Attributes:
        id (int): Unique primary key.
        user_tg_id (int): Telegram user ID (unique, FK to users.tg_id).
        port (int): Assigned HAProxy port (unique, range 10001-10999).
        activated_at (datetime): When the subscription was activated.
        expires_at (datetime): When the subscription expires.
        is_active (bool): Whether the subscription is currently active.
        is_trial_used (bool): Whether the user has used the free trial.
    """

    __tablename__ = "proxycraft_whatsapp_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_tg_id: Mapped[int] = mapped_column(
        ForeignKey("proxycraft_users.tg_id", ondelete="CASCADE"), unique=True, nullable=False
    )
    port: Mapped[int] = mapped_column(unique=True, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_trial_used: Mapped[bool] = mapped_column(default=False, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)

    def __repr__(self) -> str:
        return (
            f"<WhatsAppSubscription(id={self.id}, user_tg_id={self.user_tg_id}, "
            f"port={self.port}, expires_at={self.expires_at}, "
            f"is_active={self.is_active})>"
        )

    @classmethod
    async def get_by_user(cls, session: AsyncSession, user_tg_id: int) -> Self | None:
        query = await session.execute(
            select(WhatsAppSubscription).where(WhatsAppSubscription.user_tg_id == user_tg_id)
        )
        return query.scalar_one_or_none()

    @classmethod
    async def create(
        cls, session: AsyncSession, user_tg_id: int, port: int, expires_at: datetime, **kwargs: Any
    ) -> Self | None:
        existing = await cls.get_by_user(session=session, user_tg_id=user_tg_id)
        if existing:
            logger.warning(f"WhatsApp subscription already exists for user {user_tg_id}")
            return None

        sub = WhatsAppSubscription(
            user_tg_id=user_tg_id,
            port=port,
            expires_at=expires_at,
            **kwargs,
        )
        session.add(sub)
        try:
            await session.commit()
            logger.info(f"WhatsApp subscription created for user {user_tg_id}, port {port}")
            return sub
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Error creating WhatsApp subscription for user {user_tg_id}: {e}")
            return None

    @classmethod
    async def update_expiry(
        cls, session: AsyncSession, user_tg_id: int, expires_at: datetime
    ) -> Self | None:
        sub = await cls.get_by_user(session=session, user_tg_id=user_tg_id)
        if not sub:
            logger.warning(f"WhatsApp subscription not found for user {user_tg_id}")
            return None

        await session.execute(
            update(WhatsAppSubscription)
            .where(WhatsAppSubscription.user_tg_id == user_tg_id)
            .values(expires_at=expires_at, is_active=True)
        )
        await session.commit()
        logger.info(f"WhatsApp subscription extended for user {user_tg_id}")
        return sub

    @classmethod
    async def deactivate(cls, session: AsyncSession, user_tg_id: int) -> bool:
        sub = await cls.get_by_user(session=session, user_tg_id=user_tg_id)
        if not sub:
            return False

        await session.execute(
            update(WhatsAppSubscription)
            .where(WhatsAppSubscription.user_tg_id == user_tg_id)
            .values(is_active=False)
        )
        await session.commit()
        logger.info(f"WhatsApp subscription deactivated for user {user_tg_id}")
        return True

    @classmethod
    async def get_all_active(cls, session: AsyncSession) -> list[Self]:
        query = await session.execute(
            select(WhatsAppSubscription).where(WhatsAppSubscription.is_active == True)
        )
        return list(query.scalars().all())

    @classmethod
    async def get_expired_active(cls, session: AsyncSession) -> list[Self]:
        now = datetime.utcnow()
        query = await session.execute(
            select(WhatsAppSubscription).where(
                WhatsAppSubscription.is_active == True,
                WhatsAppSubscription.expires_at <= now,
            )
        )
        return list(query.scalars().all())

    @classmethod
    async def get_next_available_port(
        cls, session: AsyncSession, port_min: int = WHATSAPP_PORT_MIN, port_max: int = WHATSAPP_PORT_MAX
    ) -> int | None:
        """Pick a random available port from the range (security: prevents sequential enumeration)."""
        result = await session.execute(
            select(WhatsAppSubscription.port)
        )
        used_ports = set(result.scalars().all())
        all_ports = set(range(port_min, port_max + 1))
        available = list(all_ports - used_ports)

        if not available:
            logger.error("No available WhatsApp proxy ports!")
            return None

        return random.choice(available)

    @classmethod
    async def cancel(cls, session: AsyncSession, user_tg_id: int) -> Self | None:
        """Mark subscription as cancelled (stops auto-renew; stays active until expires_at)."""
        sub = await cls.get_by_user(session=session, user_tg_id=user_tg_id)
        if not sub or sub.cancelled_at is not None:
            return sub

        await session.execute(
            update(WhatsAppSubscription)
            .where(WhatsAppSubscription.user_tg_id == user_tg_id)
            .values(cancelled_at=datetime.utcnow())
        )
        await session.commit()
        await session.refresh(sub)
        logger.info(f"WhatsApp subscription cancelled for user {user_tg_id}")
        return sub

    @classmethod
    async def mark_trial_used(cls, session: AsyncSession, user_tg_id: int) -> bool:
        sub = await cls.get_by_user(session=session, user_tg_id=user_tg_id)
        if not sub:
            return False

        await session.execute(
            update(WhatsAppSubscription)
            .where(WhatsAppSubscription.user_tg_id == user_tg_id)
            .values(is_trial_used=True)
        )
        await session.commit()
        return True
