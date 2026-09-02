"""
FastAPI dependency injectors — auth, database, and permission guards.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "changeme-super-secret-key-32chars!!":
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError("JWT_SECRET_KEY must be set to a strong secret in production")
    SECRET_KEY = "changeme-super-secret-key-32chars!!"

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

_bearer = HTTPBearer(auto_error=False)


def _decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        import jwt  # PyJWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """
    FastAPI dependency: extract and validate the JWT bearer token.
    Returns the decoded user payload dict.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode_token(credentials.credentials)
    
    jti = payload.get("jti")
    if jti:
        from shared.redis.client import get_redis_client
        redis = get_redis_client()
        if await redis.exists(f"revoked_token:{jti}"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    return payload


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    """
    FastAPI dependency: optionally extract user — returns None for unauthenticated requests.
    """
    if credentials is None:
        return None
    try:
        payload = _decode_token(credentials.credentials)
        jti = payload.get("jti")
        if jti:
            from shared.redis.client import get_redis_client
            redis = get_redis_client()
            if await redis.exists(f"revoked_token:{jti}"):
                return None
        return payload
    except HTTPException:
        return None


async def require_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    FastAPI dependency: require the current user to have the 'admin' role.
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


def create_access_token(user_id: str, email: str, role: str = "user") -> str:
    """Create a JWT access token."""
    import jwt
    expire_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a longer-lived JWT refresh token."""
    import jwt
    expire_days = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    payload = {
        "sub": user_id,
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc) + timedelta(days=expire_days),
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
