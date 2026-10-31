from __future__ import annotations
import uuid
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.identity.models import User
from app.modules.identity.permissions import (
    ROLE_ADMIN,
    SCOPE_INSTITUTE,
    get_active_user_roles_and_scopes,
)

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency to extract, validate, and authorize current user from Bearer token."""
    if not auth_header or not auth_header.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header.credentials
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired. Please refresh your session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed user identifier in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status}",
        )

    # Attach active roles and scopes to user object
    roles, scopes = get_active_user_roles_and_scopes(db, user.id)
    user.active_roles = roles  # type: ignore[attr-defined]
    user.active_scopes = scopes  # type: ignore[attr-defined]
    return user

def require_roles(*allowed_roles: str):
    """Dependency factory that enforces the user possesses at least one of the specified roles."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_roles = getattr(current_user, "active_roles", [])
        if not any(role in user_roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: operation requires one of {allowed_roles} roles",
            )
        return current_user
    return role_checker

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforces institute-level admin privileges."""
    user_roles = getattr(current_user, "active_roles", [])
    if ROLE_ADMIN not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: operation strictly requires Institute Admin role",
        )
    return current_user
