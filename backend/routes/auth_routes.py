"""POST /api/register, /api/login, /api/logout"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.middleware.auth import bearer, current_user
from backend.middleware.rate_limit import limiter
from backend.models.entities import RevokedToken, User
from backend.schemas import LoginIn, RegisterIn
from backend.services.common import user_out
from backend.utils.errors import AppError
from backend.utils.time import utcnow
from cloud import auth_service
from cloud.database_service import get_db

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    limiter.check(f"register:{body.email}", settings.RATE_LIMIT_AUTH_PER_MIN)
    if db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none():
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists")
    user = User(email=body.email.lower(), name=body.name.strip(),
                password_hash=auth_service.hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    token, _, exp = auth_service.create_access_token(user.id, user.role)
    return {"token": token, "expires_at": exp.isoformat(), "user": user_out(user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    limiter.check(f"login:{body.email}", settings.RATE_LIMIT_AUTH_PER_MIN)
    user = db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none()
    # Same error for "no such user" and "wrong password" - never reveal which one it was.
    if not user or not user.is_active or not auth_service.verify_password(body.password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password")
    token, _, exp = auth_service.create_access_token(user.id, user.role)
    return {"token": token, "expires_at": exp.isoformat(), "user": user_out(user)}


@router.post("/logout")
def logout(creds=Depends(bearer), user: User = Depends(current_user), db: Session = Depends(get_db)):
    payload = auth_service.decode_token(creds.credentials)
    db.merge(RevokedToken(jti=payload["jti"], expires_at=utcnow().replace(microsecond=0)))
    db.commit()
    return {"message": "Logged out"}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)
