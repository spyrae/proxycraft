import logging
from datetime import datetime
from typing import Any, Self

from sqlalchemy import *
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from app.bot.utils.misc import generate_code

from . import Base

logger = logging.getLogger(__name__)


class Promocode(Base):
    """
    Represents a promocode entity in the database.

    Attributes:
        id (int): Unique identifier (primary key)
        code (str): Unique promocode value (32 characters max)
        duration (int): Associated subscription duration in days
        max_uses (int): Maximum number of activations (1 = single-use)
        created_at (datetime): Timestamp of creation
        activations (list[ActivatedPromocode]): List of activation records
    """

    __tablename__ = "proxycraft_promocodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(length=32), unique=True, nullable=False)
    duration: Mapped[int] = mapped_column(nullable=False)
    max_uses: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    activations: Mapped[list["ActivatedPromocode"]] = relationship(  # type: ignore
        "ActivatedPromocode", back_populates="promocode", cascade="all, delete-orphan"
    )

    @property
    def uses_count(self) -> int:
        return len(self.activations)

    @property
    def is_fully_used(self) -> bool:
        return self.uses_count >= self.max_uses

    def __repr__(self) -> str:
        return (
            f"<Promocode(id={self.id}, code='{self.code}', duration={self.duration}, "
            f"max_uses={self.max_uses}, uses={self.uses_count}, "
            f"created_at={self.created_at})>"
        )

    @classmethod
    async def get(cls, session: AsyncSession, code: str) -> Self | None:
        filter = [Promocode.code == code]
        query = await session.execute(
            select(Promocode).options(selectinload(Promocode.activations)).where(*filter)
        )
        return query.scalar_one_or_none()

    @classmethod
    async def create(cls, session: AsyncSession, code: str | None = None, **kwargs: Any) -> Self | None:
        if code is None:
            while True:
                code = generate_code()
                existing = await Promocode.get(session=session, code=code)
                if not existing:
                    break

        promocode = Promocode(code=code, **kwargs)
        session.add(promocode)

        try:
            await session.commit()
            logger.info(f"Promocode {promocode.code} created.")
            return promocode
        except IntegrityError as exception:
            await session.rollback()
            logger.error(f"Error occurred while creating promocode {promocode.code}: {exception}")
            return None

    @classmethod
    async def update(cls, session: AsyncSession, code: str, **kwargs: Any) -> Self | None:
        promocode = await Promocode.get(session=session, code=code)

        if not promocode:
            logger.warning(f"Promocode {code} not found for update.")
            return None

        filter = [Promocode.code == code]
        await session.execute(update(Promocode).where(*filter).values(**kwargs))
        await session.commit()
        logger.info(f"Promocode {code} updated.")
        return promocode

    @classmethod
    async def delete(cls, session: AsyncSession, code: str) -> bool:
        promocode = await Promocode.get(session=session, code=code)

        if promocode:
            await session.delete(promocode)
            await session.commit()
            logger.info(f"Promocode {code} deleted.")
            return True

        logger.warning(f"Promocode {code} not found for deletion.")
        return False

    @classmethod
    async def set_activated(cls, session: AsyncSession, code: str, user_id: int) -> bool:
        from .activated_promocode import ActivatedPromocode

        promocode = await Promocode.get(session=session, code=code)

        if not promocode:
            logger.warning(f"Promocode {code} not found for activation.")
            return False

        if promocode.is_fully_used:
            logger.warning(f"Promocode {code} is fully used ({promocode.uses_count}/{promocode.max_uses}).")
            return False

        if await ActivatedPromocode.has_user_activated(session, promocode.id, user_id):
            logger.warning(f"User {user_id} already activated promocode {code}.")
            return False

        activation = await ActivatedPromocode.create(session, promocode.id, user_id)
        return activation is not None

    @classmethod
    async def set_deactivated(cls, session: AsyncSession, code: str, user_id: int) -> bool:
        from .activated_promocode import ActivatedPromocode

        promocode = await Promocode.get(session=session, code=code)

        if not promocode:
            logger.warning(f"Promocode {code} not found for deactivation.")
            return False

        return await ActivatedPromocode.delete_by_promocode_and_user(
            session, promocode.id, user_id
        )
