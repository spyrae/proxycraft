import logging
from datetime import datetime
from typing import Any, Self

from sqlalchemy import ForeignKey, String, desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from . import Base

logger = logging.getLogger(__name__)


class VPNSubscription(Base):
    """Represents a single VPN subscription instance for a user."""

    __tablename__ = "proxycraft_vpn_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_tg_id: Mapped[int] = mapped_column(
        ForeignKey("proxycraft_users.tg_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vpn_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    client_email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    server_id: Mapped[int | None] = mapped_column(
        ForeignKey("proxycraft_servers.id", ondelete="SET NULL"),
        nullable=True,
    )
    devices: Mapped[int | None] = mapped_column(nullable=True)
    vpn_profile_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)

    server: Mapped["Server | None"] = relationship("Server", uselist=False)  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<VPNSubscription(id={self.id}, user_tg_id={self.user_tg_id}, vpn_id='{self.vpn_id}', "
            f"server_id={self.server_id}, client_email='{self.client_email}', devices={self.devices})>"
        )

    @classmethod
    async def get_by_id(cls, session: AsyncSession, subscription_id: int) -> Self | None:
        query = await session.execute(
            select(VPNSubscription)
            .options(selectinload(VPNSubscription.server))
            .where(VPNSubscription.id == subscription_id)
        )
        return query.scalar_one_or_none()

    @classmethod
    async def get_by_vpn_id(cls, session: AsyncSession, vpn_id: str) -> Self | None:
        query = await session.execute(
            select(VPNSubscription)
            .options(selectinload(VPNSubscription.server))
            .where(VPNSubscription.vpn_id == vpn_id)
        )
        return query.scalar_one_or_none()

    @classmethod
    async def list_by_user(cls, session: AsyncSession, user_tg_id: int) -> list[Self]:
        query = await session.execute(
            select(VPNSubscription)
            .options(selectinload(VPNSubscription.server))
            .where(VPNSubscription.user_tg_id == user_tg_id)
            .order_by(desc(VPNSubscription.created_at), desc(VPNSubscription.id))
        )
        return list(query.scalars().all())

    @classmethod
    async def get_latest_by_user(
        cls,
        session: AsyncSession,
        user_tg_id: int,
        active_first: bool = True,
    ) -> Self | None:
        subs = await cls.list_by_user(session=session, user_tg_id=user_tg_id)
        if not subs:
            return None

        if active_first:
            active_subs = [sub for sub in subs if sub.cancelled_at is None]
            if active_subs:
                return active_subs[0]

        return subs[0]

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        user_tg_id: int,
        vpn_id: str,
        client_email: str,
        server_id: int | None,
        devices: int | None,
        vpn_profile_slug: str | None = None,
        created_at: datetime | None = None,
        cancelled_at: datetime | None = None,
        **kwargs: Any,
    ) -> Self | None:
        sub = VPNSubscription(
            user_tg_id=user_tg_id,
            vpn_id=vpn_id,
            client_email=client_email,
            server_id=server_id,
            devices=devices,
            vpn_profile_slug=vpn_profile_slug,
            created_at=created_at or datetime.utcnow(),
            cancelled_at=cancelled_at,
            **kwargs,
        )
        session.add(sub)

        try:
            await session.commit()
            await session.refresh(sub)
            logger.info("VPN subscription created for user %s (subscription_id=%s)", user_tg_id, sub.id)
            return sub
        except IntegrityError as exception:
            await session.rollback()
            logger.error("Error creating VPN subscription for user %s: %s", user_tg_id, exception)
            return None

    @classmethod
    async def update(cls, session: AsyncSession, subscription_id: int, **kwargs: Any) -> Self | None:
        sub = await cls.get_by_id(session=session, subscription_id=subscription_id)
        if not sub:
            return None

        await session.execute(
            update(VPNSubscription).where(VPNSubscription.id == subscription_id).values(**kwargs)
        )
        await session.commit()
        return await cls.get_by_id(session=session, subscription_id=subscription_id)

    @classmethod
    async def cancel(cls, session: AsyncSession, subscription_id: int) -> Self | None:
        sub = await cls.get_by_id(session=session, subscription_id=subscription_id)
        if not sub or sub.cancelled_at is not None:
            return sub

        await session.execute(
            update(VPNSubscription)
            .where(VPNSubscription.id == subscription_id)
            .values(cancelled_at=datetime.utcnow())
        )
        await session.commit()
        return await cls.get_by_id(session=session, subscription_id=subscription_id)

    @classmethod
    async def has_any(cls, session: AsyncSession, user_tg_id: int) -> bool:
        query = await session.execute(
            select(func.count(VPNSubscription.id)).where(VPNSubscription.user_tg_id == user_tg_id)
        )
        return (query.scalar_one() or 0) > 0

    @classmethod
    async def list_auto_renew_candidates(cls, session: AsyncSession) -> list[Self]:
        query = await session.execute(
            select(VPNSubscription)
            .options(selectinload(VPNSubscription.server))
            .where(VPNSubscription.cancelled_at.is_(None))
            .order_by(desc(VPNSubscription.created_at), desc(VPNSubscription.id))
        )
        return list(query.scalars().all())
