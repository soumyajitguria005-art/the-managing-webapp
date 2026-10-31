from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class ApprovalTask(Base):
    __tablename__ = "approval_tasks"
    __table_args__ = {"schema": "approvals"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assigned_role: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class ApprovalEvent(Base):
    __tablename__ = "approval_events"
    __table_args__ = {"schema": "approvals"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    approval_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("approvals.approval_tasks.id"), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
