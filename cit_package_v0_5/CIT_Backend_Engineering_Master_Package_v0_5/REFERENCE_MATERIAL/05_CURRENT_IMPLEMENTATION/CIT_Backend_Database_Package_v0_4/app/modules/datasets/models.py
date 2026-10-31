from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Institute(Base):
    __tablename__ = "institutes"
    __table_args__ = {"schema": "core"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(64), server_default="Asia/Kolkata")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("institute_id", "code"), UniqueConstraint("id", "institute_id"), {"schema": "core"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    institute_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.institutes.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("institute_id", "external_dataset_id", "version_number"), UniqueConstraint("id", "institute_id"), {"schema": "core"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    institute_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.institutes.id"), nullable=False)
    external_dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    import_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class DatasetPolicy(Base):
    __tablename__ = "dataset_policy"
    __table_args__ = {"schema": "core"}
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), primary_key=True)
    priority_order: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    role_category_cap: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

class CalendarVersion(Base):
    __tablename__ = "calendar_versions"
    __table_args__ = (UniqueConstraint("id", "dataset_version_id"), UniqueConstraint("dataset_version_id"), {"schema": "core"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    fest_week_label: Mapped[str | None] = mapped_column(Text)

class CalendarDay(Base):
    __tablename__ = "calendar_days"
    __table_args__ = (UniqueConstraint("calendar_version_id", "day_code"), UniqueConstraint("calendar_version_id", "ordinal"), {"schema": "core"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.calendar_versions.id"), nullable=False)
    day_code: Mapped[str] = mapped_column(String(8), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    is_teaching_day: Mapped[bool] = mapped_column(default=True, nullable=False)

class CalendarPeriod(Base):
    __tablename__ = "calendar_periods"
    __table_args__ = (UniqueConstraint("calendar_version_id", "period_number"), {"schema": "core"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.calendar_versions.id"), nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[Any] = mapped_column(Time, nullable=False)
    ends_at: Mapped[Any] = mapped_column(Time, nullable=False)
    is_teaching_period: Mapped[bool] = mapped_column(nullable=False)
