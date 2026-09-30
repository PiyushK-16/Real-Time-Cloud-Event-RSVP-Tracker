"""Application entrypoint. Run with:  uvicorn backend.app:app --reload"""
import asyncio
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routes import (admin_routes, analytics_routes, announcement_routes, auth_routes,
                            event_routes, notification_routes, rsvp_routes)
from backend.utils.errors import AppError, app_error_handler
from backend.utils.logging import setup_logging
from cloud import auth_service
from cloud.database_service import SessionLocal, db_healthy, init_db
from realtime.realtime_service import hub, router as realtime_router

log = setup_logging()
app = FastAPI(title="Real-Time Cloud Event RSVP Tracker", version="1.0.0",
             description="Cloud Computing course project - event management with live RSVP tracking")

app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                  allow_methods=["*"], allow_headers=["*"])
app.add_exception_handler(AppError, app_error_handler)


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    log.info("%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code,
             (time.monotonic() - start) * 1000)
    return response


@app.on_event("startup")
def on_startup():
    init_db()
    hub.bind_loop(asyncio.get_event_loop())
    if settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD:
        _ensure_admin(settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD)
    log.info("Startup complete | env=%s | db_healthy=%s", settings.APP_ENV, db_healthy())


def _ensure_admin(email: str, password: str):
    from sqlalchemy import select
    from backend.models.entities import User
    db = SessionLocal()
    try:
        if not db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none():
            db.add(User(email=email.lower(), name="Administrator",
                       password_hash=auth_service.hash_password(password), role="admin"))
            db.commit()
            log.info("Bootstrapped admin account %s", email)
    finally:
        db.close()


@app.get("/healthz")
def healthz():
    """Liveness probe - never touches the database, safe for aggressive uptime pings."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """Readiness probe - confirms the database connection is actually usable."""
    healthy = db_healthy()
    return {"status": "ok" if healthy else "degraded", "database": healthy}


for r in (auth_routes.router, event_routes.router, rsvp_routes.router, announcement_routes.router,
         notification_routes.router, analytics_routes.router, admin_routes.router, realtime_router):
    app.include_router(r)

# Serve the built-in demo frontend (Option A) at "/" so the whole app runs from one process locally.
try:
    app.mount("/", StaticFiles(directory="frontend/public", html=True), name="frontend")
except RuntimeError:
    pass  # frontend/public not present yet (e.g. during import-only tooling)
