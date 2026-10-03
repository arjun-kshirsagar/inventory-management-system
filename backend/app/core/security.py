from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(subject: int, token_type: str, expires: timedelta) -> str:
    settings = get_settings()
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "exp": datetime.now(UTC) + expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    return create_token(user_id, "access", timedelta(minutes=get_settings().access_token_minutes))


def create_refresh_token(user_id: int) -> str:
    return create_token(user_id, "refresh", timedelta(days=get_settings().refresh_token_days))


def decode_token(token: str, token_type: str) -> int:
    """Return the user id from a valid token, or raise jwt.InvalidTokenError."""
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != token_type:
        raise jwt.InvalidTokenError("wrong token type")
    return int(payload["sub"])
