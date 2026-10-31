from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class BookingRequest(Base):
    __tablename__ = "booking_requests"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "external_id"),
        UniqueConstraint("id", "dataset_version_id"),
        {"schema": "booking"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requester_label: Mapped[str] = mapped_column(Text, nullable=False)
    requester_role: Mapped[str] = mapped_column(String(32), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.departments.id"))
    owner_department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.departments.id"))
    requested_category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    attendance: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_periods: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.rooms.id"))
    series_id: Mapped[str | None] = mapped_column(String(128))
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class BookingCancellation(Base):
    __tablename__ = "booking_cancellations"
    __table_args__ = {"schema": "booking"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    booking_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_requests.id"), unique=True, nullable=False)
    cancelled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_by_label: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

class BookingWindow(Base):
    __tablename__ = "booking_windows"
    __table_args__ = {"schema": "booking"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    booking_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_requests.id"), nullable=False)
    day_code: Mapped[str] = mapped_column(String(8), nullable=False)
    from_period: Mapped[int] = mapped_column(Integer, nullable=False)
    to_period: Mapped[int] = mapped_column(Integer, nullable=False)

class BookingAllowedRoomType(Base):
    __tablename__ = "booking_allowed_room_types"
    __table_args__ = {"schema": "booking"}
    booking_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_requests.id"), primary_key=True)
    room_type: Mapped[str] = mapped_column(String(64), primary_key=True)

class BookingRequiredFeature(Base):
    __tablename__ = "booking_required_features"
    __table_args__ = {"schema": "booking"}
    booking_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_requests.id"), primary_key=True)
    feature_code: Mapped[str] = mapped_column(String(64), primary_key=True)

class BookingMandatoryGroup(Base):
    __tablename__ = "booking_mandatory_groups"
    __table_args__ = (
        ForeignKeyConstraint(
            ["booking_request_id", "dataset_version_id"],
            ["booking.booking_requests.id", "booking.booking_requests.dataset_version_id"],
            name="fk_booking_mandatory_request_dataset",
        ),
        ForeignKeyConstraint(
            ["student_group_id", "dataset_version_id"],
            ["academic.student_groups.id", "academic.student_groups.dataset_version_id"],
            name="fk_booking_mandatory_group_dataset",
        ),
        {"schema": "booking"}
    )
    booking_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    student_group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

class BookingDecision(Base):
    __tablename__ = "booking_decisions"
    __table_args__ = {"schema": "booking"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    booking_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_requests.id"), nullable=False)
    decision_status: Mapped[str] = mapped_column(String(24), nullable=False)
    effective_category: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    supersedes_decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_decisions.id"))
    is_effective: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

class BookingAllocation(Base):
    __tablename__ = "booking_allocations"
    __table_args__ = {"schema": "booking"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    booking_decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_decisions.id"), nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.rooms.id"), nullable=False)
    day_code: Mapped[str] = mapped_column(String(8), nullable=False)
    start_period: Mapped[int] = mapped_column(Integer, nullable=False)
    end_period: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class BookingAlternativeResponse(Base):
    __tablename__ = "booking_alternative_responses"
    __table_args__ = {"schema": "booking"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    booking_decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_decisions.id"), unique=True, nullable=False)
    response: Mapped[str] = mapped_column(String(16), nullable=False)
    responded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class FestWeekVersion(Base):
    __tablename__ = "fest_week_versions"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "version_number"),
        {"schema": "booking"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    baseline_timetable_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"), nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.fest_week_versions.id"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class FestWeekBookingDecision(Base):
    __tablename__ = "fest_week_booking_decisions"
    __table_args__ = {"schema": "booking"}
    fest_week_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.fest_week_versions.id"), primary_key=True)
    booking_decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_decisions.id"), primary_key=True)

class SessionOverride(Base):
    __tablename__ = "session_overrides"
    __table_args__ = (
        UniqueConstraint("fest_week_version_id", "session_id"),
        {"schema": "booking"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    fest_week_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.fest_week_versions.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.teaching_sessions.id"), nullable=False)
    baseline_assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_assignments.id"), nullable=False)
    new_day: Mapped[str] = mapped_column(String(8), nullable=False)
    new_start_period: Mapped[int] = mapped_column(Integer, nullable=False)
    new_room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.rooms.id"), nullable=False)
    displaced_by_booking_decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_decisions.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class BookingPriorityEvaluation(Base):
    __tablename__ = "booking_priority_evaluations"
    __table_args__ = (
        UniqueConstraint("fest_week_version_id", "booking_request_id"),
        {"schema": "booking"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    fest_week_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.fest_week_versions.id"), nullable=False)
    booking_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking.booking_requests.id"), nullable=False)
    effective_category: Mapped[str] = mapped_column(String(64), nullable=False)
    category_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    tie_break_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
