"""
Auth router — JWT-based authentication: register, login, refresh, logout.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, Field

from services.gateway.deps import (
    create_access_token,
    create_refresh_token,
    get_current_user,
)
from shared.database.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Request / Response Schemas ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=100)
    role: str = "user"  # user | admin


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """SHA-256 + salt password hashing (use bcrypt in production)."""
    salt = os.getenv("PASSWORD_SALT", "job-platform-salt-2024")
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def _verify_password(password: str, hashed: str) -> bool:
    return _hash_password(password) == hashed


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TokenResponse:
    """Register a new user account."""
    existing = await db.users.find_one({"email": body.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user_id = str(uuid.uuid4())
    user_doc = {
        "_id": user_id,
        "email": body.email,
        "full_name": body.full_name,
        "password_hash": _hash_password(body.password),
        "role": body.role if body.role in ("user", "admin") else "user",
        "is_active": True,
        "email_verified": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "last_login": None,
        "notification_preferences": {
            "email": True,
            "in_app": True,
            "telegram": False,
        },
        "profile": {
            "headline": None,
            "skills": [],
            "experience_years": None,
            "preferred_locations": [],
            "preferred_remote_type": None,
            "preferred_salary_min": None,
        },
    }

    await db.users.insert_one(user_doc)
    logger.info(f"New user registered: {body.email} (id={user_id})")

    expire_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    access_token = create_access_token(user_id, body.email, user_doc["role"])
    refresh_token = create_refresh_token(user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email and password, receive JWT tokens."""
    user = await db.users.find_one({"email": body.email})
    if not user or not _verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Update last login
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}},
    )

    expire_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    user_id = str(user["_id"])
    access_token = create_access_token(user_id, user["email"], user.get("role", "user"))
    refresh_token = create_refresh_token(user_id)

    logger.info(f"User logged in: {body.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    body: RefreshRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TokenResponse:
    """Exchange a refresh token for a new access token."""
    import jwt

    secret = os.getenv("JWT_SECRET_KEY", "changeme-super-secret-key-32chars!!")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    try:
        payload = jwt.decode(body.refresh_token, secret, algorithms=[algorithm])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid refresh token: {e}")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    user_id = payload.get("sub")
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    expire_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    access_token = create_access_token(user_id, user["email"], user.get("role", "user"))
    new_refresh = create_refresh_token(user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=expire_minutes * 60,
    )


@router.post("/logout")
async def logout(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """
    Logout the current user.
    (Token invalidation requires a Redis blacklist in production.)
    """
    logger.info(f"User logged out: {user.get('email')}")
    return {"message": "Successfully logged out"}


@router.get("/me")
async def get_me(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Get current user info from token."""
    user_doc = await db.users.find_one({"_id": user["sub"]}, {"password_hash": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    created_at = user_doc.get("created_at")
    last_login = user_doc.get("last_login")

    return {
        "id": str(user_doc["_id"]),
        "email": user_doc.get("email"),
        "full_name": user_doc.get("full_name"),
        "role": user_doc.get("role", "user"),
        "is_active": user_doc.get("is_active", True),
        "email_verified": user_doc.get("email_verified", False),
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "last_login": last_login.isoformat() if isinstance(last_login, datetime) else last_login,
    }


@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    """Change current user's password."""
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    user_doc = await db.users.find_one({"_id": user["sub"]})
    if not user_doc or not _verify_password(current_password, user_doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    await db.users.update_one(
        {"_id": user["sub"]},
        {"$set": {"password_hash": _hash_password(new_password), "updated_at": datetime.utcnow()}},
    )
    return {"message": "Password changed successfully"}
