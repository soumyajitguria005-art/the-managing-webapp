from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email"),
        UniqueConstraint("auth_provider", "provider_subject"),
        {"schema": "identity"}
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    auth_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="LOCAL")
    provider_subject: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class UserRoleAssignment(Base):
    __tablename__ = "user_role_assignments"
    __table_args__ = {"schema": "identity"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"), nullable=False)
    role_code: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = {"schema": "identity"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = {"schema": "core"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id"))
    action: Mapped[str] = mapped_column(String(96), nullable=False)
    target_type: Mapped[str] = mapped_column(String(96), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str | None] = mapped_column(Text)
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    dataset_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.dataset_versions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
