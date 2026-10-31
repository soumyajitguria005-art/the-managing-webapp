from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class DisruptionSet(Base):
    __tablename__ = "disruption_sets"
    __table_args__ = {"schema": "change_mgmt"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.source_artifacts.id"))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    imported_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class DisruptionChange(Base):
    __tablename__ = "disruption_changes"
    __table_args__ = {"schema": "change_mgmt"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    disruption_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("change_mgmt.disruption_sets.id"), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_external_id: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)

class ChangeProposal(Base):
    __tablename__ = "change_proposals"
    __table_args__ = {"schema": "change_mgmt"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    disruption_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("change_mgmt.disruption_sets.id"), nullable=False)
    baseline_dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    target_dataset_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"))
    baseline_timetable_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"), nullable=False)
    proposed_timetable_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    movement_count: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ChangeProposalItem(Base):
    __tablename__ = "change_proposal_items"
    __table_args__ = {"schema": "change_mgmt"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    change_proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("change_mgmt.change_proposals.id"), nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("academic.teaching_sessions.id"))
    change_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    before_assignment: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_assignment: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    explanation: Mapped[str | None] = mapped_column(Text)

class ChangeApproval(Base):
    __tablename__ = "change_approvals"
    __table_args__ = {"schema": "change_mgmt"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    change_proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("change_mgmt.change_proposals.id"), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class AppliedChangeSet(Base):
    __tablename__ = "applied_change_sets"
    __table_args__ = {"schema": "change_mgmt"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    change_proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("change_mgmt.change_proposals.id"), unique=True, nullable=False)
    derived_dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"), nullable=False)
    result_timetable_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduling.timetable_versions.id"), nullable=False)
    applied_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
