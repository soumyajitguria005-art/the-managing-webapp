from __future__ import annotations
import uuid
from typing import Any, Dict, List, Optional
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.auth import get_current_user, require_admin, require_roles
from app.core.security import create_access_token
from app.db.session import get_db
from app.modules.identity.models import User, UserRoleAssignment, AuthSession, AuditEvent
from app.modules.identity.permissions import (
    get_active_user_roles_and_scopes,
    evaluate_session_modification_authority,
    evaluate_faculty_access,
    evaluate_booking_request_authority,
)
from app.modules.identity.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    PasswordChangeRequest,
    TokenResponse,
    UserCreate,
    UserUpdate,
    UserSummary,
    UserDetail,
    RoleAssignmentCreate,
    RoleAssignmentResponse,
    AuthSessionResponse,
    AuditEventResponse,
)
from app.modules.identity.service import (
    AuthService,
    UserService,
    AuthError,
    AccountLockedError,
    TokenReuseSecurityError,
)

router = APIRouter(prefix="", tags=["Identity & Access Management"])

@router.post("/auth/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticates user credentials and issues access & refresh tokens."""
    client_ip = request.client.host if request.client else None
    try:
        user = AuthService.authenticate_user(db, payload.email, payload.password, ip_address=client_ip)
    except AccountLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=e.message,
            headers={"Retry-After": str(e.lockout_seconds)}
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # Issue session & refresh token
    session, raw_refresh_token, family_id = AuthService.create_auth_session(db, user.id)

    # Get roles and scopes
    roles, scopes = get_active_user_roles_and_scopes(db, user.id)

    # Build access token JWT
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "roles": roles,
        "scopes": scopes,
    })

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserSummary(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            roles=roles,
            scopes=scopes,
        )
    )

@router.post("/auth/refresh", response_model=TokenResponse)
def refresh_token_endpoint(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Rotates the refresh token with reuse detection.
    If a compromised rotated token is submitted, the entire token family is immediately revoked.
    """
    try:
        new_session, new_raw_refresh_token, family_id, user = AuthService.rotate_refresh_token(
            db, payload.refresh_token
        )
    except TokenReuseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"token_reused\""}
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    roles, scopes = get_active_user_roles_and_scopes(db, user.id)
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "roles": roles,
        "scopes": scopes,
    })

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_raw_refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserSummary(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            roles=roles,
            scopes=scopes,
        )
    )

@router.post("/auth/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revokes active sessions for the current authenticated user."""
    AuthService.revoke_all_user_sessions(db, current_user.id, actor_id=current_user.id, reason="LOGOUT")
    return {"status": "success", "message": "Successfully logged out and revoked active sessions"}

@router.get("/auth/me", response_model=UserSummary)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the current authenticated user, active roles, and active scopes."""
    return UserSummary(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        status=current_user.status,
        roles=getattr(current_user, "active_roles", []),
        scopes=getattr(current_user, "active_scopes", []),
    )

@router.post("/auth/password-change")
def change_password_endpoint(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Changes password and invalidates all current active sessions."""
    try:
        AuthService.change_password(db, current_user.id, payload.current_password, payload.new_password)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"status": "success", "message": "Password changed successfully. All previous sessions revoked."}

@router.get("/auth/sessions", response_model=List[AuthSessionResponse])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists recent authenticated sessions for the current user."""
    sessions = db.execute(
        select(AuthSession)
        .where(AuthSession.user_id == current_user.id)
        .order_by(desc(AuthSession.created_at))
        .limit(20)
    ).scalars().all()

    now = datetime.now()
    return [
        AuthSessionResponse(
            id=s.id,
            user_id=s.user_id,
            created_at=s.created_at,
            expires_at=s.expires_at,
            revoked_at=s.revoked_at,
            is_active=s.revoked_at is None and s.expires_at > now,
        )
        for s in sessions
    ]

@router.delete("/auth/sessions/{session_id}")
def revoke_session_endpoint(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revokes a specific session."""
    session = db.get(AuthSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Only owner or admin can revoke
    is_admin = "admin" in getattr(current_user, "active_roles", [])
    if session.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Cannot revoke another user's session")

    AuthService.revoke_session(db, session_id, actor_id=current_user.id)
    return {"status": "success", "message": f"Session {session_id} successfully revoked"}

# ---------- User Management (Admin Only) ----------

@router.get("/users", response_model=List[UserSummary])
def list_users(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: lists all registered users with active roles and scopes."""
    users = db.execute(select(User).order_by(User.email)).scalars().all()
    out = []
    for u in users:
        roles, scopes = get_active_user_roles_and_scopes(db, u.id)
        out.append(UserSummary(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            status=u.status,
            roles=roles,
            scopes=scopes,
        ))
    return out

@router.post("/users", response_model=UserDetail, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: provisions a new user with password and optional role assignment."""
    try:
        user = UserService.create_user(
            db,
            email=payload.email,
            display_name=payload.display_name,
            password=payload.password,
            status=payload.status,
            creator_id=admin_user.id,
        )
        if payload.initial_role:
            UserService.assign_role(
                db,
                user_id=user.id,
                role_code=payload.initial_role.role_code,
                scope_type=payload.initial_role.scope_type,
                scope_id=payload.initial_role.scope_id,
                granted_by=admin_user.id,
            )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    assignments = db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user.id,
            UserRoleAssignment.revoked_at.is_(None)
        )
    ).scalars().all()
    roles = sorted(list({a.role_code for a in assignments}))

    return UserDetail(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        auth_provider=user.auth_provider,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=roles,
        role_assignments=[RoleAssignmentResponse.model_validate(a) for a in assignments]
    )

@router.get("/users/{user_id}", response_model=UserDetail)
def get_user_detail(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Gets detailed profile and role assignments for a user (admin or self)."""
    is_admin = "admin" in getattr(current_user, "active_roles", [])
    if current_user.id != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    assignments = db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user.id,
            UserRoleAssignment.revoked_at.is_(None)
        )
    ).scalars().all()
    roles = sorted(list({a.role_code for a in assignments}))

    return UserDetail(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        auth_provider=user.auth_provider,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=roles,
        role_assignments=[RoleAssignmentResponse.model_validate(a) for a in assignments]
    )

@router.post("/users/{user_id}/activate")
def activate_user_endpoint(
    user_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: activates a user account."""
    try:
        user = UserService.activate_user(db, user_id, actor_id=admin_user.id)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"status": "success", "message": f"User {user.email} is now ACTIVE"}

@router.post("/users/{user_id}/deactivate")
def deactivate_user_endpoint(
    user_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: deactivates a user account and revokes all active sessions."""
    try:
        user = UserService.deactivate_user(db, user_id, actor_id=admin_user.id)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"status": "success", "message": f"User {user.email} is now DISABLED and sessions revoked"}

@router.post("/users/{user_id}/roles", response_model=RoleAssignmentResponse)
def assign_role_endpoint(
    user_id: uuid.UUID,
    payload: RoleAssignmentCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: assigns an official role and scope to a user."""
    try:
        assignment = UserService.assign_role(
            db,
            user_id=user_id,
            role_code=payload.role_code,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            granted_by=admin_user.id,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return RoleAssignmentResponse.model_validate(assignment)

@router.delete("/users/{user_id}/roles/{assignment_id}")
def revoke_role_endpoint(
    user_id: uuid.UUID,
    assignment_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: revokes an active role assignment."""
    try:
        assignment = UserService.revoke_role(db, assignment_id, actor_id=admin_user.id)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"status": "success", "message": f"Role assignment {assignment_id} revoked"}

# ---------- Verification / Scope Inspection Endpoints ----------

@router.get("/auth/verify-session-authority/{session_id}")
def verify_session_authority(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluates whether the caller has authority to modify the given teaching session.
    Enforces joint/cross-department scheduling authority invariants.
    """
    authorized, reason = evaluate_session_modification_authority(db, current_user.id, session_id)
    return {
        "user_id": str(current_user.id),
        "session_id": str(session_id),
        "authorized": authorized,
        "reason": reason,
    }

@router.get("/auth/verify-faculty-authority/{faculty_id}")
def verify_faculty_authority(
    faculty_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluates whether the caller has authority to manage the given faculty resource."""
    authorized, reason = evaluate_faculty_access(db, current_user.id, faculty_id)
    return {
        "user_id": str(current_user.id),
        "faculty_id": str(faculty_id),
        "authorized": authorized,
        "reason": reason,
    }

@router.get("/auth/verify-booking-authority/{booking_id}")
def verify_booking_authority(
    booking_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluates whether the caller has authority to manage the given booking request."""
    authorized, reason = evaluate_booking_request_authority(db, current_user.id, booking_id)
    return {
        "user_id": str(current_user.id),
        "booking_id": str(booking_id),
        "authorized": authorized,
        "reason": reason,
    }

@router.get("/auth/audit-logs", response_model=List[AuditEventResponse])
def get_audit_logs(
    admin_user: User = Depends(require_admin),
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Admin-only: queries recent security and identity audit log events."""
    events = db.execute(
        select(AuditEvent)
        .order_by(desc(AuditEvent.created_at))
        .limit(min(limit, 200))
    ).scalars().all()

    return [AuditEventResponse.model_validate(e) for e in events]
