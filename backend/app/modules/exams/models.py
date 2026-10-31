from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class ExamRecord(Base):
    __tablename__ = "exam_records"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "external_id"),
        UniqueConstraint("id", "dataset_version_id"),
        {"schema": "exams"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

class ExamCourse(Base):
    __tablename__ = "exam_courses"
    __table_args__ = {"schema": "exams"}
    exam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.exam_records.id"), primary_key=True)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.courses.id"), primary_key=True)

class ExamGroup(Base):
    __tablename__ = "exam_groups"
    __table_args__ = {"schema": "exams"}
    exam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.exam_records.id"), primary_key=True)
    student_group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.student_groups.id"), primary_key=True)

class ExamScheduleVersion(Base):
    __tablename__ = "exam_schedule_versions"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "version_number"),
        ForeignKeyConstraint(
            ["calendar_version_id", "dataset_version_id"],
            ["core.calendar_versions.id", "core.calendar_versions.dataset_version_id"],
        ),
        {"schema": "exams"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.exam_schedule_versions.id"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ExamAssignment(Base):
    __tablename__ = "exam_assignments"
    __table_args__ = (
        UniqueConstraint("exam_schedule_version_id", "exam_id"),
        {"schema": "exams"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    exam_schedule_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.exam_schedule_versions.id"), nullable=False)
    exam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.exam_records.id"), nullable=False)
    day_code: Mapped[str] = mapped_column(String(8), nullable=False)
    session_code: Mapped[str] = mapped_column(String(16), nullable=False)

class ExamRoomAllocation(Base):
    __tablename__ = "exam_room_allocations"
    __table_args__ = (
        UniqueConstraint("exam_assignment_id", "room_id"),
        {"schema": "exams"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    exam_assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.exam_assignments.id"), nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.rooms.id"), nullable=False)
    allocated_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
