"""Tiny in-memory sliding-window rate limiter (per key). Use Redis/API Gateway when scaled out."""
import time
from collections import defaultdict, deque
from threading import Lock

from backend.utils.errors import AppError


class RateLimiter:
    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window: int = 60):
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                raise AppError(429, "RATE_LIMITED", "Too many requests, slow down and retry shortly")
            q.append(now)

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
