"""Central configuration. Every secret comes from environment variables (12-factor style)."""
import os
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


class Settings:
    APP_ENV = os.getenv("APP_ENV", "development")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./event_rsvp.db")
    # Dev fallback is random per process so tokens are never signed with a known constant.
    JWT_SECRET = os.getenv("JWT_SECRET") or os.urandom(32).hex()
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_MINUTES = _int("JWT_EXPIRE_MINUTES", 60)
    PASSWORD_HASH_ITERATIONS = _int("PASSWORD_HASH_ITERATIONS", 200_000)
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if o.strip()]
    RATE_LIMIT_AUTH_PER_MIN = _int("RATE_LIMIT_AUTH_PER_MIN", 30)
    RATE_LIMIT_RSVP_PER_MIN = _int("RATE_LIMIT_RSVP_PER_MIN", 60)
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


settings = Settings()
