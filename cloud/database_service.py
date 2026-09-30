"""Cloud database layer.

Local  : SQLite file (zero setup).
Cloud  : any PostgreSQL (Supabase, Neon, RDS...) by changing DATABASE_URL only.

Concurrency notes
- SQLite: every transaction starts with BEGIN IMMEDIATE, so writers are serialized.
- PostgreSQL: rsvp_service takes a row lock (SELECT ... FOR UPDATE) on the event row.
- In both cases seats are claimed with an atomic conditional UPDATE (see rsvp_service).
"""
import logging
import time
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import settings

log = logging.getLogger("rsvp.db")


class Base(DeclarativeBase):
    pass


def _normalize(url: str) -> str:
    # Render/Heroku style URLs use the "postgres://" scheme which SQLAlchemy rejects.
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def make_engine(url: str):
    url = _normalize(url)
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(engine, "connect")
        def _on_connect(dbapi_conn, _):
            dbapi_conn.isolation_level = None  # we control BEGIN ourselves
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        @event.listens_for(engine, "begin")
        def _on_begin(conn):
            conn.exec_driver_sql("BEGIN IMMEDIATE")

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = make_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db():
    from backend.models import entities  # noqa: F401  (registers tables)
    Base.metadata.create_all(engine)


def get_db():
    """FastAPI dependency: one session per request, rolled back on any error."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_with_retry(db, fn, attempts=3, base_delay=0.1):
    """Retry transient DB failures (locked DB, dropped connection) with exponential backoff."""
    for i in range(attempts):
        try:
            return fn()
        except OperationalError as exc:
            db.rollback()
            if i == attempts - 1:
                log.error("DB operation failed after %s attempts: %s", attempts, exc)
                raise
            delay = base_delay * (2 ** i)
            log.warning("Transient DB error (attempt %s/%s), retrying in %.2fs", i + 1, attempts, delay)
            time.sleep(delay)


def db_healthy() -> bool:
    try:
        with engine.connect() as c:
            c.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False
