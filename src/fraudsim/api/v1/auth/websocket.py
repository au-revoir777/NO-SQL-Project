"""
Origins and WebSocket authentication for the original API.

Browsers allowed to call the API cross-origin are listed in CORS_ORIGINS
(comma-separated; default: the Next.js app on :3000 and the Vite dashboard dev
server on :5173). The same list guards the /ws handshake against cross-site
WebSocket hijacking: a handshake whose Origin is neither the API's own host nor
an allowed origin is refused before the session cookie is even read.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from fastapi import WebSocket
from starlette.concurrency import run_in_threadpool

from fraudsim import appdb
from fraudsim.api.v1.auth.deps import authenticate
from fraudsim.api.v1.auth.security import ACCESS_COOKIE, TokenClaims
from fraudsim.api.v1.errors import ApiError
from fraudsim.appdb.models import User

DEFAULT_ORIGINS = "http://localhost:3000,http://localhost:5173"

# WebSocket close codes (4000-4999 are application-defined).
WS_UNAUTHENTICATED = 4401
WS_FORBIDDEN_ORIGIN = 4403


def cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", DEFAULT_ORIGINS)
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def origin_allowed(origin: str | None, host: str | None) -> bool:
    """Same-host or listed origins only. Non-browser clients send no Origin."""
    if not origin:
        return True
    if host and urlsplit(origin).netloc == host:
        return True
    return origin.rstrip("/") in cors_origins()


def _authenticate_sync(token: str | None) -> tuple[User, TokenClaims]:
    db = appdb.open_session()
    try:
        return authenticate(token, db)
    finally:
        db.close()


async def authenticate_websocket(websocket: WebSocket) -> tuple[User, TokenClaims] | None:
    """
    Accept the socket and return the user, or refuse it and return None.

    A foreign Origin is refused during the handshake (HTTP 403). A missing or
    invalid session is accepted and then closed with WS_UNAUTHENTICATED, so the
    browser client can tell "sign in again" apart from a network failure.
    """
    if not origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host")):
        await websocket.close(code=WS_FORBIDDEN_ORIGIN)
        return None
    try:
        auth = await run_in_threadpool(_authenticate_sync, websocket.cookies.get(ACCESS_COOKIE))
    except ApiError as exc:
        await websocket.accept()
        await websocket.close(code=WS_UNAUTHENTICATED, reason=exc.code)
        return None
    await websocket.accept()
    return auth
