from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt

from app.core.config import (
    JWT_SECRET,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

def hash_password(plain_password: str) -> str:
    """Hashes a plain text password using bcrypt with 12 work rounds."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a bcrypt hash."""
    if not hashed_password or not plain_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def generate_random_token() -> str:
    """Generates a cryptographically strong, URL-safe random token string."""
    return secrets.token_urlsafe(48)

def hash_token(raw_token: str) -> str:
    """Hashes a raw refresh token using SHA-256 for persistent database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def _json_safe(val: Any) -> Any:
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, dict):
        return {k: _json_safe(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [_json_safe(v) for v in val]
    return val

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Creates a signed JWT access token with an expiration timestamp."""
    to_encode = {k: _json_safe(v) for k, v in data.items()}
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "access",
    })
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise jwt.InvalidTokenError("Token type must be 'access'")
        return payload
    except jwt.ExpiredSignatureError:
        raise
    except jwt.PyJWTError as e:
        raise jwt.InvalidTokenError(str(e)) from e
