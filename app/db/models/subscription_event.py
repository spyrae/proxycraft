import logging
from datetime import datetime
from typing import Self

from sqlalchemy import BigInteger, String, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from . import Base

logger = logging.getLogger(__name__)


class SubscriptionEvent(Base):
    """
    Tracks subscription notification events to prevent duplicate notifications
    within the same subscription cycle.

    Attributes:
        id: Primary key.
        tg_id: Telegram user ID.
        stage: Notification stage (t_5d, t_3d, t_1d, t_0, t_p3d, t_p14d).
        expiry_time: Copy of expiry_time from 3X-UI (ms) at the time of recording.
        sent_at: Timestamp when the notification was sent.
    """

    __tablename__ = "proxycraft_subscription_events"
    __table_args__ = (
        UniqueConstraint("tg_id", "expiry_time", "stage", name="uq_subscription_event_cycle"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stage: Mapped[str] = mapped_column(String(10), nullable=False)
    expiry_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<SubscriptionEvent(id={self.id}, tg_id={self.tg_id}, "
            f"stage='{self.stage}', expiry_time={self.expiry_time}, sent_at={self.sent_at})>"
        )

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        tg_id: int,
        stage: str,
        expiry_time: int,
    ) -> Self | None:
        event = cls(tg_id=tg_id, stage=stage, expiry_time=expiry_time)
        session.add(event)
        try:
            await session.commit()
            logger.debug(f"SubscriptionEvent created: tg_id={tg_id}, stage={stage}")
            return event
        except Exception as e:
            await session.rollback()
            logger.warning(f"SubscriptionEvent already exists or error: tg_id={tg_id}, stage={stage}: {e}")
            return None

    @classmethod
    async def exists(
        cls,
        session: AsyncSession,
        tg_id: int,
        expiry_time: int,
        stage: str,
    ) -> bool:
        query = await session.execute(
            select(cls).where(
                cls.tg_id == tg_id,
                cls.expiry_time == expiry_time,
                cls.stage == stage,
            )
        )
        return query.scalar_one_or_none() is not None

    @classmethod
    async def get_latest_by_stage(
        cls,
        session: AsyncSession,
        tg_id: int,
        stage: str,
    ) -> Self | None:
        query = await session.execute(
            select(cls)
            .where(cls.tg_id == tg_id, cls.stage == stage)
            .order_by(cls.sent_at.desc())
            .limit(1)
        )
        return query.scalar_one_or_none()
