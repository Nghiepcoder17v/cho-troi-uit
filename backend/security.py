"""Băm mật khẩu (bcrypt) và JWT."""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
from database import get_db

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError(
        "Thiếu JWT_SECRET (>= 32 ký tự) trong .env. Tạo bằng: "
        'python -c "import secrets; print(secrets.token_urlsafe(32))"'
    )
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

ACCESS_TOKEN_COOKIE_NAME = "access_token"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# Hash giả để việc "email không tồn tại" tốn thời gian tương đương "sai mật khẩu"
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), (password_hash or _DUMMY_HASH).encode("utf-8")) and bool(
            password_hash
        )
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> models.User:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if token is None:
        raise _unauthorized("Thiếu token xác thực")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized("Token không hợp lệ hoặc đã hết hạn")
    user = db.get(models.User, user_id)
    if user is None:
        raise _unauthorized("Tài khoản không tồn tại")
    return user


def require_moderator(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[models.User, str]:
    """Resolve active authority from SQL on every request; never trust JWT role claims."""
    role_codes = set(
        db.scalars(
            select(models.UserRoleAssignment.role_code).where(
                models.UserRoleAssignment.user_id == current_user.user_id,
                models.UserRoleAssignment.revoked_at.is_(None),
            )
        ).all()
    )
    if "ADMIN" in role_codes:
        return current_user, "ADMIN"
    if "MODERATOR" in role_codes:
        return current_user, "MODERATOR"
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền kiểm duyệt")
