"""Authentication + role-based authorization dependencies."""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.models.entities import RevokedToken, User
from backend.utils.errors import AppError, forbidden
from cloud.auth_service import decode_token
from cloud.database_service import SessionLocal, get_db

bearer = HTTPBearer(auto_error=False)


def is_revoked(jti: str) -> bool:
    db = SessionLocal()
    try:
        return db.get(RevokedToken, jti) is not None
    finally:
        db.close()


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    """Authentication: WHO is calling? Validates signature, expiry, revocation and account status."""
    if creds is None:
        raise AppError(401, "UNAUTHORIZED", "Authentication required")
    payload = decode_token(creds.credentials)
    if db.get(RevokedToken, payload.get("jti", "")):
        raise AppError(401, "TOKEN_REVOKED", "You have been logged out")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise AppError(401, "UNAUTHORIZED", "Account not available")
    return user


def require_role(*roles: str):
    """Authorization: WHAT may the caller do? Role comes from the DB row, never from the client."""
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise forbidden(f"This action requires role: {', '.join(roles)}")
        return user
    return dep
