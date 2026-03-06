import logging
from datetime import datetime
from typing import Self

from sqlalchemy import ForeignKey, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

logger = logging.getLogger(__name__)


class ActivatedPromocode(Base):
    """
    M2M table tracking individual promocode activations by users.

    Attributes:
        id (int): Primary key.
        promocode_id (int): FK to proxycraft_promocodes.
        user_tg_id (int): FK to proxycraft_users.tg_id.
        activated_at (datetime): When the activation occurred.
    """

    __tablename__ = "proxycraft_activated_promocodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    promocode_id: Mapped[int] = mapped_column(
        ForeignKey("proxycraft_promocodes.id", ondelete="CASCADE"), nullable=False
    )
    user_tg_id: Mapped[int] = mapped_column(
        ForeignKey("proxycraft_users.tg_id", ondelete="CASCADE"), nullable=False
    )
    activated_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    promocode: Mapped["Promocode"] = relationship("Promocode", back_populates="activations")  # type: ignore
    user: Mapped["User"] = relationship("User", back_populates="promocode_activations")  # type: ignore

    def __repr__(self) -> str:
        return (
            f"<ActivatedPromocode(id={self.id}, promocode_id={self.promocode_id}, "
            f"user_tg_id={self.user_tg_id}, activated_at={self.activated_at})>"
        )

    @classmethod
    async def get_count_by_promocode(cls, session: AsyncSession, promocode_id: int) -> int:
        query = await session.execute(
            select(func.count()).where(ActivatedPromocode.promocode_id == promocode_id)
        )
        return query.scalar() or 0

    @classmethod
    async def has_user_activated(
        cls, session: AsyncSession, promocode_id: int, user_tg_id: int
    ) -> bool:
        query = await session.execute(
            select(func.count()).where(
                ActivatedPromocode.promocode_id == promocode_id,
                ActivatedPromocode.user_tg_id == user_tg_id,
            )
        )
        return (query.scalar() or 0) > 0

    @classmethod
    async def create(
        cls, session: AsyncSession, promocode_id: int, user_tg_id: int
    ) -> Self | None:
        activation = ActivatedPromocode(promocode_id=promocode_id, user_tg_id=user_tg_id)
        session.add(activation)
        try:
            await session.commit()
            logger.info(f"Promocode {promocode_id} activated by user {user_tg_id}.")
            return activation
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Failed to create activation for promocode {promocode_id}: {e}")
            return None

    @classmethod
    async def delete_by_promocode_and_user(
        cls, session: AsyncSession, promocode_id: int, user_tg_id: int
    ) -> bool:
        from sqlalchemy import delete as sa_delete

        result = await session.execute(
            sa_delete(ActivatedPromocode).where(
                ActivatedPromocode.promocode_id == promocode_id,
                ActivatedPromocode.user_tg_id == user_tg_id,
            )
        )
        await session.commit()
        return result.rowcount > 0
