"""Authentication primitives: password hashing (PBKDF2) and JWT access tokens."""
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from backend.config import settings
from backend.utils.errors import AppError


def hash_password(password: str, iterations: int | None = None) -> str:
    iterations = iterations or settings.PASSWORD_HASH_ITERATIONS
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)  # constant-time compare
    except Exception:
        return False


def create_access_token(user_id: int, role: str, expires_minutes: int | None = None) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES if expires_minutes is None else expires_minutes)
    jti = uuid.uuid4().hex
    payload = {"sub": str(user_id), "role": role, "jti": jti, "iat": now, "exp": exp}
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, jti, exp.replace(tzinfo=None)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AppError(401, "TOKEN_EXPIRED", "Session expired, please log in again")
    except jwt.PyJWTError:
        raise AppError(401, "INVALID_TOKEN", "Invalid authentication token")
