from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from resume_agent.db.models import UserRecord

_SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production-please")
_ALGORITHM = "HS256"
_TOKEN_EXPIRE_DAYS = 30

_bearer = HTTPBearer()


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "exp": expire},
        _SECRET_KEY,
        algorithm=_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ── FastAPI dependency — resolves current user from Bearer token ──────────────

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    payload = decode_token(creds.credentials)
    return {"id": int(payload["sub"]), "email": payload["email"]}


# ── DB helpers (called from api.py with a session) ───────────────────────────

async def create_user(session: AsyncSession, email: str, password: str) -> UserRecord:
    existing = await session.execute(
        select(UserRecord).where(UserRecord.email == email.lower())
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = UserRecord(email=email.lower(), hashed_password=hash_password(password))
    session.add(user)
    await session.flush()
    return user


async def authenticate_user(
    session: AsyncSession, email: str, password: str
) -> UserRecord:
    result = await session.execute(
        select(UserRecord).where(UserRecord.email == email.lower())
    )
    user = result.scalars().first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return user
