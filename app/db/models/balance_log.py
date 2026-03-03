import logging
from datetime import datetime
from typing import Self

from sqlalchemy import ForeignKey, String, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from . import Base

logger = logging.getLogger(__name__)


class BalanceLog(Base):
    """Audit log for balance changes (top-ups, purchases, auto-renewals, refunds)."""

    __tablename__ = "vpncraft_balance_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(ForeignKey("vpncraft_users.tg_id"), nullable=False)
    amount: Mapped[int] = mapped_column(nullable=False)  # kopecks, positive=topup, negative=purchase
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # topup, purchase, auto_renew, refund
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<BalanceLog(id={self.id}, tg_id={self.tg_id}, amount={self.amount}, "
            f"type='{self.type}', description='{self.description}')>"
        )

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        tg_id: int,
        amount: int,
        type: str,
        description: str | None = None,
        payment_id: str | None = None,
    ) -> Self | None:
        entry = BalanceLog(
            tg_id=tg_id,
            amount=amount,
            type=type,
            description=description,
            payment_id=payment_id,
        )
        session.add(entry)

        try:
            await session.commit()
            logger.info(f"BalanceLog created: tg_id={tg_id}, amount={amount}, type={type}")
            return entry
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Error creating BalanceLog for {tg_id}: {e}")
            return None

    @classmethod
    async def get_by_user(cls, session: AsyncSession, tg_id: int, limit: int = 50) -> list[Self]:
        query = await session.execute(
            select(BalanceLog)
            .where(BalanceLog.tg_id == tg_id)
            .order_by(BalanceLog.created_at.desc())
            .limit(limit)
        )
        return query.scalars().all()
