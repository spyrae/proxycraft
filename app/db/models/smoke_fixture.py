import logging
from datetime import datetime
from typing import Any, Self

from sqlalchemy import ForeignKey, String, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from . import Base

logger = logging.getLogger(__name__)


class SmokeFixture(Base):
    """Registry of stable smoke-test fixtures used by deploy verification."""

    __tablename__ = "proxycraft_smoke_fixtures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    product: Mapped[str] = mapped_column(String(32), nullable=False)
    location: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_tg_id: Mapped[int] = mapped_column(
        ForeignKey("proxycraft_users.tg_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vpn_subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("proxycraft_vpn_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    mtproto_subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("proxycraft_mtproto_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    whatsapp_subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("proxycraft_whatsapp_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        nullable=False,
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<SmokeFixture(id={self.id}, key='{self.key}', product='{self.product}', "
            f"location='{self.location}', user_tg_id={self.user_tg_id})>"
        )

    @classmethod
    async def get_by_key(cls, session: AsyncSession, key: str) -> Self | None:
        query = await session.execute(select(SmokeFixture).where(SmokeFixture.key == key))
        return query.scalar_one_or_none()

    @classmethod
    async def list_all(cls, session: AsyncSession) -> list[Self]:
        query = await session.execute(select(SmokeFixture).order_by(SmokeFixture.key))
        return list(query.scalars().all())

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        *,
        key: str,
        product: str,
        user_tg_id: int,
        location: str | None = None,
        vpn_subscription_id: int | None = None,
        mtproto_subscription_id: int | None = None,
        whatsapp_subscription_id: int | None = None,
    ) -> Self | None:
        fixture = SmokeFixture(
            key=key,
            product=product,
            user_tg_id=user_tg_id,
            location=location,
            vpn_subscription_id=vpn_subscription_id,
            mtproto_subscription_id=mtproto_subscription_id,
            whatsapp_subscription_id=whatsapp_subscription_id,
        )
        session.add(fixture)
        try:
            await session.commit()
            await session.refresh(fixture)
            logger.info("Smoke fixture %s created.", key)
            return fixture
        except IntegrityError as exception:
            await session.rollback()
            logger.error("Failed to create smoke fixture %s: %s", key, exception)
            return None

    @classmethod
    async def update(cls, session: AsyncSession, key: str, **kwargs: Any) -> Self | None:
        fixture = await cls.get_by_key(session=session, key=key)
        if not fixture:
            logger.warning("Smoke fixture %s not found for update.", key)
            return None

        await session.execute(
            update(SmokeFixture)
            .where(SmokeFixture.key == key)
            .values(**kwargs, updated_at=func.now())
        )
        await session.commit()
        return await cls.get_by_key(session=session, key=key)

