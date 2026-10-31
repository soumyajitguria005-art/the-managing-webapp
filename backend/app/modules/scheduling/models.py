from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class TimetableVersion(Base):
    __tablename__ = "timetable_versions"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "version_number"),
        UniqueConstraint("id", "dataset_version_id"),
        ForeignKeyConstraint(
            ["calendar_version_id", "dataset_version_id"],
            ["core.calendar_versions.id", "core.calendar_versions.dataset_version_id"],
        ),
        {"schema": "scheduling"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class TimetableGenerationRequest(Base):
    __tablename__ = "timetable_generation_requests"
    __table_args__ = (
        UniqueConstraint("requested_by", "idempotency_key"),
        {"schema": "scheduling"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    calendar_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.calendar_versions.id"), nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    request_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="QUEUED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class GenerationScope(Base):
    __tablename__ = "generation_scopes"
    __table_args__ = {"schema": "scheduling"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    generation_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_generation_requests.id"), unique=True, nullable=False)
    baseline_timetable_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"))
    preserve_outside_scope: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scope_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    scope_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class GenerationScopeDepartment(Base):
    __tablename__ = "generation_scope_departments"
    __table_args__ = {"schema": "scheduling"}
    generation_scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.generation_scopes.id"), primary_key=True)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.departments.id"), primary_key=True)

class GenerationScopeSession(Base):
    __tablename__ = "generation_scope_sessions"
    __table_args__ = {"schema": "scheduling"}
    generation_scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.generation_scopes.id"), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.teaching_sessions.id"), primary_key=True)
    inclusion_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    is_movable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

class LockedAssignment(Base):
    __tablename__ = "locked_assignments"
    __table_args__ = {"schema": "scheduling"}
    generation_scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.generation_scopes.id"), primary_key=True)
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_assignments.id"), primary_key=True)
    lock_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline_hash: Mapped[str] = mapped_column(String(64), nullable=False)

class TimetableAssignment(Base):
    __tablename__ = "timetable_assignments"
    __table_args__ = (
        UniqueConstraint("timetable_version_id", "session_id"),
        UniqueConstraint("id", "timetable_version_id"),
        UniqueConstraint("id", "timetable_version_id", "dataset_version_id", name="uq_assignment_id_timetable_dataset"),
        ForeignKeyConstraint(
            ["timetable_version_id", "dataset_version_id"],
            ["scheduling.timetable_versions.id", "scheduling.timetable_versions.dataset_version_id"],
            name="fk_assignment_timetable_dataset",
        ),
        ForeignKeyConstraint(
            ["session_id", "dataset_version_id"],
            ["academic.teaching_sessions.id", "academic.teaching_sessions.dataset_version_id"],
            name="fk_assignment_session_dataset",
        ),
        ForeignKeyConstraint(
            ["room_id", "dataset_version_id"],
            ["academic.rooms.id", "academic.rooms.dataset_version_id"],
            name="fk_assignment_room_dataset",
        ),
        {"schema": "scheduling"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    timetable_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    day_code: Mapped[str] = mapped_column(String(8), nullable=False)
    start_period: Mapped[int] = mapped_column(Integer, nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class TimetableOccupancy(Base):
    __tablename__ = "timetable_occupancy"
    __table_args__ = (
        UniqueConstraint("timetable_version_id", "resource_type", "occupancy_key", "day_code", "period_number"),
        {"schema": "scheduling"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    timetable_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(24), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    day_code: Mapped[str] = mapped_column(String(8), nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_assignments.id"), nullable=False)
    occupancy_key: Mapped[str] = mapped_column(String(160), nullable=False)

class SolverRun(Base):
    __tablename__ = "solver_runs"
    __table_args__ = {"schema": "scheduling"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    generation_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_generation_requests.id"))
    timetable_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"))
    solver_name: Mapped[str] = mapped_column(String(64), nullable=False)
    solver_version: Mapped[str | None] = mapped_column(String(64))
    random_seed: Mapped[int | None] = mapped_column(BigInteger)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer)
    worker_count: Mapped[int | None] = mapped_column(Integer)
    objective_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    solver_status: Mapped[str] = mapped_column(String(24), nullable=False)
    runtime_ms: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class SolverMetric(Base):
    __tablename__ = "solver_metrics"
    __table_args__ = {"schema": "scheduling"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    solver_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.solver_runs.id"), nullable=False)
    hard_violation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    soft_s1: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    soft_s2: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    soft_s3: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    soft_s4: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    soft_s5: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    soft_s6: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    objective_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ValidationRun(Base):
    __tablename__ = "validation_runs"
    __table_args__ = {"schema": "scheduling"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    validator_name: Mapped[str] = mapped_column(String(64), nullable=False)
    validator_version: Mapped[str | None] = mapped_column(String(64))
    source_checksum: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    hard_violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    soft_score: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    report_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ValidationViolation(Base):
    __tablename__ = "validation_violations"
    __table_args__ = {"schema": "scheduling"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    validation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.validation_runs.id"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_external_id: Mapped[str | None] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

class TimetablePublication(Base):
    __tablename__ = "timetable_publications"
    __table_args__ = {"schema": "scheduling"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    timetable_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"), nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    supersedes_publication_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_publications.id"))

class PublishedTimetablePointer(Base):
    __tablename__ = "published_timetable_pointers"
    __table_args__ = {"schema": "scheduling"}
    institute_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.institutes.id"), primary_key=True)
    timetable_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
