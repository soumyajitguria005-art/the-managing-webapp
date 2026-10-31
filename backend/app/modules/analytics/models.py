from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = {"schema": "analytics"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"))
    timetable_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"))
    fest_week_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.fest_week_versions.id"))
    metric_key: Mapped[str] = mapped_column(String(96), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
