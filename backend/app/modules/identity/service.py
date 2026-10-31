from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    MAX_FAILED_LOGIN_ATTEMPTS,
    LOCKOUT_DURATION_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.core.security import (
    hash_password,
    verify_password,
    generate_random_token,
    hash_token,
    create_access_token,
)
from app.modules.identity.models import User, UserRoleAssignment, AuthSession, AuditEvent
from app.modules.identity.permissions import (
    ROLE_ADMIN,
    OFFICIAL_ROLES,
    OFFICIAL_SCOPES,
    SCOPE_INSTITUTE,
    SCOPE_DEPARTMENT,
    SCOPE_CLUB,
    SCOPE_RESOURCE,
    get_active_user_roles_and_scopes,
)

class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class AccountLockedError(AuthError):
    def __init__(self, message: str, lockout_seconds: int = 0):
        super().__init__(message, status_code=429)
        self.lockout_seconds = lockout_seconds

class TokenReuseSecurityError(AuthError):
    def __init__(self, message: str):
        super().__init__(message, status_code=401)

def record_audit_event(
    db: Session,
    action: str,
    target_type: str,
    target_id: Optional[uuid.UUID] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    reason: Optional[str] = None,
    before_snapshot: Optional[Dict[str, Any]] = None,
    after_snapshot: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[uuid.UUID] = None,
) -> AuditEvent:
    """Persists a structured security/audit event into core.audit_events."""
    event = AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        correlation_id=correlation_id,
    )
    db.add(event)
    db.flush()
    return event

def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

class AuthService:
    @staticmethod
    def check_lockout(db: Session, email: str, user_id: Optional[uuid.UUID] = None) -> Tuple[bool, int]:
        """
        Determines if an account is locked out based on recent consecutive failed login attempts.
        Returns (is_locked, remaining_lockout_seconds).
        """
        now_utc = datetime.now(timezone.utc)
        window_start = now_utc - timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        
        # Count failed logins within lockout window
        stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.action == "AUTH_LOGIN_FAILED",
            AuditEvent.created_at >= window_start
        )
        if user_id:
            stmt = stmt.where(AuditEvent.target_id == user_id)
        else:
            # Query by email inside before/after snapshots if user_id unknown
            stmt = stmt.where(AuditEvent.reason.like(f"%{email}%"))

        failed_count = db.execute(stmt).scalar() or 0
        if failed_count >= MAX_FAILED_LOGIN_ATTEMPTS:
            # Calculate most recent failure timestamp
            recent_stmt = select(func.max(AuditEvent.created_at)).where(
                AuditEvent.action == "AUTH_LOGIN_FAILED",
                AuditEvent.created_at >= window_start
            )
            if user_id:
                recent_stmt = recent_stmt.where(AuditEvent.target_id == user_id)
            else:
                recent_stmt = recent_stmt.where(AuditEvent.reason.like(f"%{email}%"))
            last_failed_at = db.execute(recent_stmt).scalar()
            
            if last_failed_at:
                last_failed_utc = _as_utc(last_failed_at)
                elapsed = (now_utc - last_failed_utc).total_seconds()
                remaining = max(1, int((LOCKOUT_DURATION_MINUTES * 60) - elapsed))
                return True, remaining
            return True, LOCKOUT_DURATION_MINUTES * 60
        return False, 0

    @classmethod
    def authenticate_user(
        cls,
        db: Session,
        email: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> User:
        """
        Authenticates a user by email and password, enforcing:
        - Rate limiting and consecutive failed attempt lockout.
        - Active account status verification.
        - Comprehensive audit logging.
        """
        normalized_email = email.strip().lower()
        user = db.execute(
            select(User).where(func.lower(User.email) == normalized_email)
        ).scalar_one_or_none()

        # Check account lockout
        is_locked, remaining_sec = cls.check_lockout(db, normalized_email, user.id if user else None)
        if is_locked:
            record_audit_event(
                db,
                action="AUTH_LOGIN_REJECTED_LOCKED",
                target_type="USER",
                target_id=user.id if user else None,
                reason=f"Account locked: {remaining_sec} seconds remaining",
                after_snapshot={"email": normalized_email, "remaining_seconds": remaining_sec}
            )
            db.commit()
            raise AccountLockedError(
                f"Account is temporarily locked due to excessive failed login attempts. Please try again in {remaining_sec} seconds.",
                lockout_seconds=remaining_sec
            )

        if not user or not verify_password(password, user.password_hash or ""):
            # Record failed login
            record_audit_event(
                db,
                action="AUTH_LOGIN_FAILED",
                target_type="USER",
                target_id=user.id if user else None,
                reason=f"Invalid credentials for {normalized_email}",
                after_snapshot={"email": normalized_email, "ip": ip_address}
            )
            db.commit()

            # Check if this failure triggered lockout
            is_now_locked, now_remaining = cls.check_lockout(db, normalized_email, user.id if user else None)
            if is_now_locked:
                record_audit_event(
                    db,
                    action="AUTH_ACCOUNT_LOCKED",
                    target_type="USER",
                    target_id=user.id if user else None,
                    reason=f"Maximum failed login attempts ({MAX_FAILED_LOGIN_ATTEMPTS}) reached",
                    after_snapshot={"email": normalized_email, "locked_until_seconds": now_remaining}
                )
                db.commit()
                raise AccountLockedError(
                    f"Account locked: maximum failed login attempts exceeded. Locked for {now_remaining} seconds.",
                    lockout_seconds=now_remaining
                )
            raise AuthError("Invalid email or password", status_code=401)

        # Check user status
        if user.status != "ACTIVE":
            record_audit_event(
                db,
                action="AUTH_LOGIN_REJECTED_STATUS",
                target_type="USER",
                target_id=user.id,
                reason=f"User status is {user.status}",
                after_snapshot={"status": user.status}
            )
            db.commit()
            raise AuthError(f"Account is {user.status}. Please contact an administrator.", status_code=403)

        # Record successful login
        record_audit_event(
            db,
            action="AUTH_LOGIN_SUCCESS",
            target_type="USER",
            target_id=user.id,
            actor_user_id=user.id,
            after_snapshot={"email": user.email, "ip": ip_address}
        )
        db.commit()
        return user

    @classmethod
    def create_auth_session(
        cls,
        db: Session,
        user_id: uuid.UUID,
        family_id: Optional[uuid.UUID] = None
    ) -> Tuple[AuthSession, str, uuid.UUID]:
        """Creates a new authenticated session with an opaque refresh token and family tracking."""
        raw_refresh_token = generate_random_token()
        token_hash = hash_token(raw_refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        session = AuthSession(
            user_id=user_id,
            refresh_token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(session)
        db.flush()

        assigned_family_id = family_id or session.id

        record_audit_event(
            db,
            action="AUTH_SESSION_CREATED",
            target_type="AUTH_SESSION",
            target_id=session.id,
            actor_user_id=user_id,
            correlation_id=assigned_family_id,
            after_snapshot={"expires_at": expires_at.isoformat()}
        )
        db.commit()
        return session, raw_refresh_token, assigned_family_id

    @classmethod
    def rotate_refresh_token(
        cls,
        db: Session,
        raw_token: str
    ) -> Tuple[AuthSession, str, uuid.UUID, User]:
        """
        Executes refresh token rotation with immediate reuse detection.
        - If a token is presented that has already been rotated (revoked_at is set):
          REVOCATION: Entire session family is immediately revoked, protecting against token theft!
        - If valid: old token is marked revoked, new token created in same family.
        """
        token_hash = hash_token(raw_token)
        session = db.execute(
            select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        ).scalar_one_or_none()

        if not session:
            raise AuthError("Invalid refresh token", status_code=401)

        # Retrieve token family ID from audit trail
        audit_row = db.execute(
            select(AuditEvent.correlation_id).where(
                AuditEvent.target_id == session.id,
                AuditEvent.target_type == "AUTH_SESSION",
                AuditEvent.correlation_id.is_not(None)
            ).order_by(AuditEvent.created_at)
        ).scalars().first()
        family_id = audit_row or session.id

        # REUSE DETECTION: Token has already been revoked!
        if session.revoked_at is not None:
            # Revoke entire family and all active sessions for this compromised user
            related_session_ids = db.execute(
                select(AuditEvent.target_id).where(
                    AuditEvent.correlation_id == family_id,
                    AuditEvent.target_type == "AUTH_SESSION"
                )
            ).scalars().all()

            target_ids = list(set([session.id] + [sid for sid in related_session_ids if sid]))
            
            # Revoke sessions in family
            db.execute(
                update(AuthSession)
                .where(AuthSession.id.in_(target_ids), AuthSession.revoked_at.is_(None))
                .values(revoked_at=func.now())
            )
            # Revoke all active user sessions for safety
            db.execute(
                update(AuthSession)
                .where(AuthSession.user_id == session.user_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=func.now())
            )

            record_audit_event(
                db,
                action="AUTH_REFRESH_TOKEN_REUSE_DETECTED",
                target_type="AUTH_SESSION",
                target_id=session.id,
                actor_user_id=session.user_id,
                correlation_id=family_id,
                reason="Compromised refresh token reuse detected. All active sessions in family revoked."
            )
            db.commit()
            raise TokenReuseSecurityError(
                "Security Alert: Compromised refresh token reuse detected. All sessions in this token family have been permanently revoked."
            )

        # Check expiration
        now_utc = datetime.now(timezone.utc)
        session_expires_utc = _as_utc(session.expires_at)
        if session_expires_utc and session_expires_utc < now_utc:
            session.revoked_at = now_utc
            db.commit()
            raise AuthError("Refresh token has expired. Please log in again.", status_code=401)

        # Check user status
        user = db.get(User, session.user_id)
        if not user or user.status != "ACTIVE":
            session.revoked_at = now_utc
            db.commit()
            raise AuthError("User account is inactive or disabled.", status_code=403)

        # Mark current session as rotated/revoked
        session.revoked_at = now_utc
        db.flush()

        # Issue new token in same family
        new_session, new_raw_token, _ = cls.create_auth_session(db, session.user_id, family_id=family_id)

        record_audit_event(
            db,
            action="AUTH_TOKEN_ROTATED",
            target_type="AUTH_SESSION",
            target_id=new_session.id,
            actor_user_id=session.user_id,
            correlation_id=family_id,
            before_snapshot={"old_session_id": str(session.id)},
            after_snapshot={"new_session_id": str(new_session.id)}
        )
        db.commit()
        return new_session, new_raw_token, family_id, user

    @classmethod
    def revoke_session(cls, db: Session, session_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None) -> bool:
        """Revokes a single authenticated session."""
        session = db.get(AuthSession, session_id)
        if not session:
            return False
        if session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            record_audit_event(
                db,
                action="AUTH_SESSION_REVOKED",
                target_type="AUTH_SESSION",
                target_id=session.id,
                actor_user_id=actor_id or session.user_id,
                reason="Explicit session revocation / logout"
            )
            db.commit()
        return True

    @classmethod
    def revoke_all_user_sessions(
        cls,
        db: Session,
        user_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        reason: str = "LOGOUT_ALL"
    ) -> int:
        """Revokes all active sessions for a user (e.g. on password change)."""
        now = datetime.now(timezone.utc)
        result = db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        revoked_count = result.rowcount
        record_audit_event(
            db,
            action="AUTH_ALL_SESSIONS_REVOKED",
            target_type="USER",
            target_id=user_id,
            actor_user_id=actor_id or user_id,
            reason=f"{reason}: {revoked_count} active sessions terminated"
        )
        db.commit()
        return revoked_count

    @classmethod
    def change_password(
        cls,
        db: Session,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str
    ) -> User:
        """Changes user password and invalidates all existing active sessions."""
        user = db.get(User, user_id)
        if not user:
            raise AuthError("User not found", status_code=404)

        if not verify_password(current_password, user.password_hash or ""):
            record_audit_event(
                db,
                action="AUTH_PASSWORD_CHANGE_FAILED",
                target_type="USER",
                target_id=user.id,
                actor_user_id=user.id,
                reason="Incorrect current password"
            )
            db.commit()
            raise AuthError("Current password verification failed", status_code=400)

        if len(new_password) < 8:
            raise AuthError("New password must be at least 8 characters long", status_code=400)

        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now()
        db.flush()

        # Invalidate all active sessions
        cls.revoke_all_user_sessions(db, user.id, actor_id=user.id, reason="PASSWORD_CHANGE")

        record_audit_event(
            db,
            action="AUTH_PASSWORD_CHANGED",
            target_type="USER",
            target_id=user.id,
            actor_user_id=user.id,
            reason="User password successfully updated"
        )
        db.commit()
        return user

class UserService:
    @classmethod
    def create_user(
        cls,
        db: Session,
        email: str,
        display_name: str,
        password: str,
        status: str = "ACTIVE",
        auth_provider: str = "LOCAL",
        creator_id: Optional[uuid.UUID] = None
    ) -> User:
        """Registers or provisions a new user with secure password hash."""
        normalized_email = email.strip().lower()
        existing = db.execute(
            select(User).where(func.lower(User.email) == normalized_email)
        ).scalar_one_or_none()
        if existing:
            raise AuthError(f"User with email '{normalized_email}' already exists", status_code=409)

        user = User(
            email=normalized_email,
            display_name=display_name.strip(),
            password_hash=hash_password(password),
            status=status,
            auth_provider=auth_provider
        )
        db.add(user)
        db.flush()

        record_audit_event(
            db,
            action="USER_CREATED",
            target_type="USER",
            target_id=user.id,
            actor_user_id=creator_id,
            after_snapshot={"email": user.email, "display_name": user.display_name, "status": user.status}
        )
        db.commit()
        return user

    @classmethod
    def activate_user(cls, db: Session, user_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None) -> User:
        user = db.get(User, user_id)
        if not user:
            raise AuthError(f"User {user_id} not found", status_code=404)
        old_status = user.status
        user.status = "ACTIVE"
        user.updated_at = datetime.now()
        record_audit_event(
            db,
            action="USER_ACTIVATED",
            target_type="USER",
            target_id=user.id,
            actor_user_id=actor_id,
            before_snapshot={"status": old_status},
            after_snapshot={"status": user.status}
        )
        db.commit()
        return user

    @classmethod
    def deactivate_user(cls, db: Session, user_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None) -> User:
        user = db.get(User, user_id)
        if not user:
            raise AuthError(f"User {user_id} not found", status_code=404)
        old_status = user.status
        user.status = "DISABLED"
        user.updated_at = datetime.now()
        db.flush()

        # Revoke all active sessions
        AuthService.revoke_all_user_sessions(db, user.id, actor_id=actor_id, reason="USER_DEACTIVATED")

        record_audit_event(
            db,
            action="USER_DEACTIVATED",
            target_type="USER",
            target_id=user.id,
            actor_user_id=actor_id,
            before_snapshot={"status": old_status},
            after_snapshot={"status": user.status}
        )
        db.commit()
        return user

    @classmethod
    def assign_role(
        cls,
        db: Session,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: str,
        scope_id: Optional[uuid.UUID] = None,
        granted_by: Optional[uuid.UUID] = None
    ) -> UserRoleAssignment:
        """Assigns an official role and scope to a user."""
        if role_code not in OFFICIAL_ROLES:
            raise AuthError(f"Invalid role code '{role_code}'. Allowed: {sorted(list(OFFICIAL_ROLES))}", status_code=400)
        if scope_type not in OFFICIAL_SCOPES:
            raise AuthError(f"Invalid scope type '{scope_type}'. Allowed: {sorted(list(OFFICIAL_SCOPES))}", status_code=400)

        # Validate scope consistency
        if scope_type == SCOPE_INSTITUTE and scope_id is not None:
            scope_id = None  # Institute scope is global
        if scope_type in (SCOPE_DEPARTMENT, SCOPE_RESOURCE) and scope_id is None:
            raise AuthError(f"Scope type '{scope_type}' requires a non-null scope_id UUID", status_code=400)

        assignment = UserRoleAssignment(
            user_id=user_id,
            role_code=role_code,
            scope_type=scope_type,
            scope_id=scope_id,
            granted_by=granted_by,
        )
        db.add(assignment)
        db.flush()

        record_audit_event(
            db,
            action="ROLE_ASSIGNED",
            target_type="USER_ROLE_ASSIGNMENT",
            target_id=assignment.id,
            actor_user_id=granted_by,
            after_snapshot={
                "user_id": str(user_id),
                "role_code": role_code,
                "scope_type": scope_type,
                "scope_id": str(scope_id) if scope_id else None
            }
        )
        db.commit()
        return assignment

    @classmethod
    def revoke_role(cls, db: Session, assignment_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None) -> UserRoleAssignment:
        assignment = db.get(UserRoleAssignment, assignment_id)
        if not assignment:
            raise AuthError(f"Role assignment {assignment_id} not found", status_code=404)
        if assignment.revoked_at is None:
            assignment.revoked_at = datetime.now()
            record_audit_event(
                db,
                action="ROLE_REVOKED",
                target_type="USER_ROLE_ASSIGNMENT",
                target_id=assignment.id,
                actor_user_id=actor_id,
                reason="Role assignment revoked"
            )
            db.commit()
        return assignment
