"""Real-time layer: an in-process pub/sub hub exposed over WebSockets and Server-Sent Events.

Flow:  RSVP committed in DB  ->  hub.publish_threadsafe("event:<id>", payload)
       -> every subscribed WebSocket/SSE client gets the new counts instantly.

Channels:  event:<id>  (public counts for one event)   user:<id>  (private notifications)

Scaling note: this hub lives in one process. With several server instances you replace the
hub internals with Redis Pub/Sub (or use Supabase Realtime / API Gateway WebSocket) - the
rest of the code does not change. See docs/scalability.md.
"""
import asyncio
import json
import logging
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from backend.utils.errors import AppError
from cloud.auth_service import decode_token
from cloud.database_service import SessionLocal

log = logging.getLogger("rsvp.realtime")


class RealtimeHub:
    def __init__(self):
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop):
        self._loop = loop

    def subscribe(self, channel: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs[channel].add(q)
        return q

    def unsubscribe(self, channel: str, q: asyncio.Queue):
        self._subs[channel].discard(q)
        if not self._subs[channel]:
            self._subs.pop(channel, None)

    def subscriber_count(self, channel: str) -> int:
        return len(self._subs.get(channel, ()))

    async def publish(self, channel: str, message: dict):
        for q in list(self._subs.get(channel, ())):
            if q.full():  # slow client: drop its oldest message instead of blocking everyone
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(message)

    def publish_threadsafe(self, channel: str, message: dict):
        """Callable from ordinary (sync) service code running in worker threads.
        Never raises: a real-time failure must not fail the RSVP that already committed."""
        try:
            if self._loop is not None and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.publish(channel, message), self._loop)
        except Exception:  # pragma: no cover
            log.exception("realtime publish failed for %s", channel)


hub = RealtimeHub()
router = APIRouter()


def _build_snapshot(event_id: int, user_id: int):
    from backend.models.entities import Event, User
    from backend.services import rsvp_service
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        event = db.get(Event, event_id)
        if not user or not user.is_active or not event:
            return None
        if event.status == "DRAFT" and event.organizer_id != user.id and user.role != "admin":
            return None
        return {"type": "snapshot", **rsvp_service.snapshot(db, event)}
    finally:
        db.close()


def _auth_user_id(token: str) -> int | None:
    try:
        payload = decode_token(token)
    except AppError:
        return None
    from backend.middleware.auth import is_revoked
    if is_revoked(payload.get("jti", "")):
        return None
    return int(payload["sub"])


async def _pump(ws: WebSocket, q: asyncio.Queue):
    while True:
        await ws.send_json(await q.get())


async def _serve(ws: WebSocket, channel: str, first_message: dict | None):
    await ws.accept()
    q = hub.subscribe(channel)
    try:
        if first_message:
            await ws.send_json(first_message)  # snapshot => client never misses state on (re)connect
        sender = asyncio.create_task(_pump(ws, q))
        try:
            while True:
                await ws.receive_text()  # client "ping" keep-alives; also detects disconnect
        finally:
            sender.cancel()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unsubscribe(channel, q)


@router.websocket("/ws/events/{event_id}")
async def ws_event(ws: WebSocket, event_id: int, token: str = ""):
    uid = await run_in_threadpool(_auth_user_id, token) if token else None
    snap = await run_in_threadpool(_build_snapshot, event_id, uid) if uid else None
    if snap is None:
        await ws.close(code=4401)
        return
    await _serve(ws, f"event:{event_id}", snap)


@router.websocket("/ws/me")
async def ws_me(ws: WebSocket, token: str = ""):
    uid = await run_in_threadpool(_auth_user_id, token) if token else None
    if uid is None:
        await ws.close(code=4401)
        return
    await _serve(ws, f"user:{uid}", {"type": "hello"})


@router.get("/api/events/{event_id}/stream")
async def sse_event(event_id: int, token: str = ""):
    """Server-Sent Events alternative (one-way, plain HTTP). Same payloads as the WebSocket."""
    uid = await run_in_threadpool(_auth_user_id, token) if token else None
    snap = await run_in_threadpool(_build_snapshot, event_id, uid) if uid else None
    if snap is None:
        raise AppError(401, "UNAUTHORIZED", "Valid token and visible event required")

    async def gen():
        q = hub.subscribe(f"event:{event_id}")
        try:
            yield f"data: {json.dumps(snap)}\n\n"
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            hub.unsubscribe(f"event:{event_id}", q)

    return StreamingResponse(gen(), media_type="text/event-stream")
