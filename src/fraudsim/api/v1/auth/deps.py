"""
FastAPI dependencies that enforce authentication, roles and CSRF on /api/v1.

Every protected router is mounted with `Depends(require_user)` (analyst or
admin) or `Depends(require_admin)`, plus `Depends(csrf_protect)`; the check
happens on the server for every request, whatever the UI shows.
"""

from __future__ import annotations

import hmac
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from fraudsim import appdb
from fraudsim.api.v1.auth.security import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    TokenError,
    decode_token,
)
from fraudsim.api.v1.errors import ApiError
from fraudsim.appdb.models import Role, User

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_db() -> Iterator[Session]:
    yield from appdb.session_scope()


DB = Annotated[Session, Depends(get_db)]


def require_user(request: Request, db: DB) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise ApiError(401, "unauthenticated", "Sign in to use this endpoint")
    try:
        claims = decode_token(token, "access")
    except TokenError as exc:
        raise ApiError(401, exc.code, exc.message) from exc
    user = db.get(User, claims.user_id)
    if user is None or not user.is_active or user.token_version != claims.token_version:
        raise ApiError(401, "session_revoked", "Session is no longer valid; sign in again")
    request.state.user = user
    return user


CurrentUser = Annotated[User, Depends(require_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != Role.ADMIN:
        raise ApiError(403, "forbidden", "This action requires the admin role")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def csrf_protect(request: Request) -> None:
    """Double-submit check for state-changing requests."""
    if request.method in SAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get(CSRF_HEADER, "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise ApiError(403, "csrf_failed", "Missing or invalid CSRF token")


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
