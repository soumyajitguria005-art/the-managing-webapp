from __future__ import annotations
import uuid
from decimal import Decimal
from typing import Any
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("dataset_version_id", "external_id"), UniqueConstraint("id", "dataset_version_id"), {"schema": "academic"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    building: Mapped[str | None] = mapped_column(Text)
    room_type: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    accessible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

class RoomFeature(Base):
    __tablename__ = "room_features"
    __table_args__ = {"schema": "academic"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)

class RoomFeatureAssignment(Base):
    __tablename__ = "room_feature_assignments"
    __table_args__ = {"schema": "academic"}
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.rooms.id"), primary_key=True)
    feature_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.room_features.id"), primary_key=True)

class RoomAllowedUse(Base):
    __tablename__ = "room_allowed_uses"
    __table_args__ = {"schema": "academic"}
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.rooms.id"), primary_key=True)
    use_code: Mapped[str] = mapped_column(String(32), primary_key=True)

class Faculty(Base):
    __tablename__ = "faculty"
    __table_args__ = (UniqueConstraint("dataset_version_id", "external_id"), UniqueConstraint("id", "dataset_version_id"), {"schema": "academic"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.departments.id"))
    max_hours_per_day: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=4)
    needs_accessible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

class StudentGroup(Base):
    __tablename__ = "student_groups"
    __table_args__ = (UniqueConstraint("dataset_version_id", "external_id"), UniqueConstraint("id", "dataset_version_id"), {"schema": "academic"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.departments.id"))
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    needs_accessible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("dataset_version_id", "external_id"), UniqueConstraint("id", "dataset_version_id"), {"schema": "academic"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.departments.id"))
    year: Mapped[int | None] = mapped_column(Integer)
    lecture_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    tutorial_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    lab_blocks: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)

class TeachingSession(Base):
    __tablename__ = "teaching_sessions"
    __table_args__ = (UniqueConstraint("dataset_version_id", "external_id"), UniqueConstraint("id", "dataset_version_id"), {"schema": "academic"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.courses.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.faculty.id"))
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_periods: Mapped[int] = mapped_column(Integer, nullable=False)
    needs_accessible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    basket_slot: Mapped[str | None] = mapped_column(String(128))
    fixed_day: Mapped[str | None] = mapped_column(String(8))
    fixed_start_period: Mapped[int | None] = mapped_column(Integer)
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
