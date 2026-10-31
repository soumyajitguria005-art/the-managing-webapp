from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Institute(Base):
    __tablename__ = "institutes"
    __table_args__ = {"schema": "core"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("institute_id", "code"),
        UniqueConstraint("id", "institute_id"),
        {"schema": "core"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    institute_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.institutes.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)

class SourceArtifact(Base):
    __tablename__ = "source_artifacts"
    __table_args__ = {"schema": "core"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("institute_id", "external_dataset_id", "version_number"),
        UniqueConstraint("id", "institute_id"),
        {"schema": "core"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    institute_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.institutes.id"), nullable=False)
    external_dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_dataset_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"))
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.source_artifacts.id"))
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    import_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    application_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    derived_from_change_set_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    imported_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class DatasetPolicy(Base):
    __tablename__ = "dataset_policy"
    __table_args__ = {"schema": "core"}
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), primary_key=True)
    priority_order: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    role_category_cap: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

class DatasetActivation(Base):
    __tablename__ = "dataset_activations"
    __table_args__ = {"schema": "core"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    institute_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.institutes.id"), nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    activated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)

class CalendarVersion(Base):
    __tablename__ = "calendar_versions"
    __table_args__ = (
        UniqueConstraint("id", "dataset_version_id"),
        UniqueConstraint("dataset_version_id"),
        {"schema": "core"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    fest_week_label: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class CalendarDay(Base):
    __tablename__ = "calendar_days"
    __table_args__ = (
        UniqueConstraint("calendar_version_id", "day_code"),
        UniqueConstraint("calendar_version_id", "ordinal"),
        UniqueConstraint("id", "calendar_version_id"),
        {"schema": "core"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.calendar_versions.id"), nullable=False)
    day_code: Mapped[str] = mapped_column(String(8), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    is_teaching_day: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class CalendarPeriod(Base):
    __tablename__ = "calendar_periods"
    __table_args__ = (
        UniqueConstraint("calendar_version_id", "period_number"),
        UniqueConstraint("id", "calendar_version_id"),
        {"schema": "core"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.calendar_versions.id"), nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[Any] = mapped_column(Time, nullable=False)
    ends_at: Mapped[Any] = mapped_column(Time, nullable=False)
    is_teaching_period: Mapped[bool] = mapped_column(Boolean, nullable=False)

class CalendarBreak(Base):
    __tablename__ = "calendar_breaks"
    __table_args__ = (
        UniqueConstraint("calendar_version_id", "break_code"),
        {"schema": "core"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.calendar_versions.id"), nullable=False)
    break_code: Mapped[str] = mapped_column(String(32), nullable=False)
    after_period: Mapped[int | None] = mapped_column(Integer)
    starts_at: Mapped[Any] = mapped_column(Time, nullable=False)
    ends_at: Mapped[Any] = mapped_column(Time, nullable=False)

class CalendarLabStartPeriod(Base):
    __tablename__ = "calendar_lab_start_periods"
    __table_args__ = (
        ForeignKeyConstraint(
            ["calendar_version_id", "period_number"],
            ["core.calendar_periods.calendar_version_id", "core.calendar_periods.period_number"],
        ),
        {"schema": "core"}
    )
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.calendar_versions.id"), primary_key=True)
    period_number: Mapped[int] = mapped_column(Integer, primary_key=True)

class CalendarEventPeriod(Base):
    __tablename__ = "calendar_event_periods"
    __table_args__ = (
        ForeignKeyConstraint(
            ["calendar_version_id", "period_number"],
            ["core.calendar_periods.calendar_version_id", "core.calendar_periods.period_number"],
        ),
        {"schema": "core"}
    )
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.calendar_versions.id"), primary_key=True)
    period_number: Mapped[int] = mapped_column(Integer, primary_key=True)

class CalendarExamDay(Base):
    __tablename__ = "calendar_exam_days"
    __table_args__ = (
        UniqueConstraint("calendar_version_id", "day_code"),
        UniqueConstraint("calendar_version_id", "ordinal"),
        {"schema": "core"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.calendar_versions.id"), nullable=False)
    day_code: Mapped[str] = mapped_column(String(8), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)

class CalendarExamSession(Base):
    __tablename__ = "calendar_exam_sessions"
    __table_args__ = (
        UniqueConstraint("calendar_version_id", "session_code"),
        UniqueConstraint("id", "calendar_version_id"),
        {"schema": "core"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.calendar_versions.id"), nullable=False)
    session_code: Mapped[str] = mapped_column(String(16), nullable=False)
    starts_at: Mapped[Any] = mapped_column(Time, nullable=False)
    ends_at: Mapped[Any] = mapped_column(Time, nullable=False)
