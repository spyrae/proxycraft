import logging
from datetime import datetime
from typing import Any, Self
from uuid import uuid4

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

logger = logging.getLogger(__name__)


class GeoProbeRun(Base):
    __tablename__ = "proxycraft_geo_probe_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    results: Mapped[list["GeoProbeResult"]] = relationship(
        "GeoProbeResult",
        back_populates="run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<GeoProbeRun(id={self.id}, run_uuid='{self.run_uuid}', trigger='{self.trigger}', "
            f"status='{self.status}')>"
        )

    @classmethod
    async def create(cls, session: AsyncSession, *, trigger: str, details: dict[str, Any] | None = None) -> Self:
        run = GeoProbeRun(trigger=trigger, details=details)
        session.add(run)
        await session.commit()
        await session.refresh(run)
        logger.info("Geo probe run %s created.", run.run_uuid)
        return run

    @classmethod
    async def update_status(
        cls,
        session: AsyncSession,
        *,
        run_id: int,
        status: str,
        summary: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> Self | None:
        await session.execute(
            update(GeoProbeRun)
            .where(GeoProbeRun.id == run_id)
            .values(
                status=status,
                summary=summary,
                details=details,
                completed_at=func.now(),
            )
        )
        await session.commit()
        query = await session.execute(select(GeoProbeRun).where(GeoProbeRun.id == run_id))
        return query.scalar_one_or_none()

    @classmethod
    async def latest(cls, session: AsyncSession) -> Self | None:
        query = await session.execute(select(GeoProbeRun).order_by(GeoProbeRun.started_at.desc(), GeoProbeRun.id.desc()))
        return query.scalars().first()


class GeoProbeResult(Base):
    __tablename__ = "proxycraft_geo_probe_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("proxycraft_geo_probe_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    probe_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    probe_region: Mapped[str] = mapped_column(String(32), nullable=False)
    probe_node: Mapped[str | None] = mapped_column(String(128), nullable=True)
    probe_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    probe_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    probe_asn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    throughput_kbps: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    run: Mapped[GeoProbeRun] = relationship("GeoProbeRun", back_populates="results")

    def __repr__(self) -> str:
        return (
            f"<GeoProbeResult(id={self.id}, run_id={self.run_id}, scope='{self.probe_scope}', "
            f"region='{self.probe_region}', product='{self.product}', status='{self.status}')>"
        )

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        *,
        run_id: int,
        probe_scope: str,
        probe_region: str,
        product: str,
        target_type: str,
        endpoint: str,
        status: str,
        probe_node: str | None = None,
        probe_country: str | None = None,
        probe_city: str | None = None,
        probe_asn: str | None = None,
        latency_ms: float | None = None,
        http_status: int | None = None,
        throughput_kbps: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> Self:
        result = GeoProbeResult(
            run_id=run_id,
            probe_scope=probe_scope,
            probe_region=probe_region,
            probe_node=probe_node,
            probe_country=probe_country,
            probe_city=probe_city,
            probe_asn=probe_asn,
            product=product,
            target_type=target_type,
            endpoint=endpoint,
            status=status,
            latency_ms=latency_ms,
            http_status=http_status,
            throughput_kbps=throughput_kbps,
            details=details,
        )
        session.add(result)
        await session.commit()
        await session.refresh(result)
        return result

