from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., description="User's login email address")
    password: str = Field(..., min_length=1, description="Plain text password")

class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(..., min_length=1, description="Opaque refresh token")

class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")

class RoleScopeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    role_code: str
    scope_type: str
    scope_id: Optional[uuid.UUID] = None

class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str
    status: str
    roles: List[str] = Field(default_factory=list)
    scopes: List[RoleScopeItem] = Field(default_factory=list)

class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSummary

class RoleAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_code: str = Field(..., pattern="^(admin|department_coordinator|faculty|club)$")
    scope_type: str = Field(..., pattern="^(institute|department|club|resource)$")
    scope_id: Optional[uuid.UUID] = None

class RoleAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    role_code: str
    scope_type: str
    scope_id: Optional[uuid.UUID] = None
    granted_by: Optional[uuid.UUID] = None
    granted_at: datetime
    revoked_at: Optional[datetime] = None

class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    display_name: str
    password: str = Field(..., min_length=8)
    status: str = "ACTIVE"
    initial_role: Optional[RoleAssignmentCreate] = None

class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(ACTIVE|INVITED|SUSPENDED|DISABLED)$")

class UserDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str
    auth_provider: str
    status: str
    created_at: datetime
    updated_at: datetime
    roles: List[str] = Field(default_factory=list)
    role_assignments: List[RoleAssignmentResponse] = Field(default_factory=list)

class AuthSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    is_active: bool

class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    actor_user_id: Optional[uuid.UUID] = None
    action: str
    target_type: str
    target_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None
    correlation_id: Optional[uuid.UUID] = None
    created_at: datetime
