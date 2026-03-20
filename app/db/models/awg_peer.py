import logging
from datetime import datetime
from typing import Any, Self

from sqlalchemy import ForeignKey, String, Text, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from . import Base

logger = logging.getLogger(__name__)


class AWGPeer(Base):
    """AmneziaWG peer linked to a VPN subscription."""

    __tablename__ = "proxycraft_awg_peers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vpn_subscription_id: Mapped[int] = mapped_column(
        ForeignKey("proxycraft_vpn_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    private_key: Mapped[str] = mapped_column(Text, nullable=False)
    public_key: Mapped[str] = mapped_column(String(64), nullable=False)
    preshared_key: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_ip: Mapped[str] = mapped_column(String(18), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<AWGPeer(id={self.id}, sub={self.vpn_subscription_id}, "
            f"ip={self.assigned_ip}, active={self.is_active})>"
        )

    @classmethod
    async def get_by_subscription(cls, session: AsyncSession, vpn_subscription_id: int) -> Self | None:
        result = await session.execute(
            select(cls).where(cls.vpn_subscription_id == vpn_subscription_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        vpn_subscription_id: int,
        private_key: str,
        public_key: str,
        preshared_key: str,
        assigned_ip: str,
    ) -> Self | None:
        peer = cls(
            vpn_subscription_id=vpn_subscription_id,
            private_key=private_key,
            public_key=public_key,
            preshared_key=preshared_key,
            assigned_ip=assigned_ip,
        )
        session.add(peer)
        try:
            await session.commit()
            await session.refresh(peer)
            logger.info("AWG peer created for subscription %s (ip=%s)", vpn_subscription_id, assigned_ip)
            return peer
        except IntegrityError as e:
            await session.rollback()
            logger.error("Error creating AWG peer for subscription %s: %s", vpn_subscription_id, e)
            return None

    @classmethod
    async def deactivate(cls, session: AsyncSession, vpn_subscription_id: int) -> bool:
        result = await session.execute(
            update(cls)
            .where(cls.vpn_subscription_id == vpn_subscription_id)
            .values(is_active=False)
        )
        await session.commit()
        return result.rowcount > 0

    @classmethod
    async def get_max_ip_suffix(cls, session: AsyncSession) -> int:
        """Get the highest IP suffix allocated (e.g., 10.10.0.X → returns X)."""
        result = await session.execute(select(cls.assigned_ip))
        ips = [row[0] for row in result.all()]
        if not ips:
            return 1  # server is .1, first peer gets .2
        suffixes = []
        for ip in ips:
            parts = ip.split(".")
            if len(parts) == 4:
                try:
                    suffixes.append(int(parts[3]))
                except ValueError:
                    pass
        return max(suffixes) if suffixes else 1
