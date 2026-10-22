"""
Passwords, tokens and cookies for /api/v1.

- Passwords: argon2id (argon2-cffi defaults).
- Sessions: a short-lived access JWT and a longer refresh JWT, each in an
  httpOnly, SameSite=Lax cookie (Secure unless COOKIE_SECURE=0). Both carry the
  user's token_version, so logout, deactivation and role changes revoke them.
- CSRF: double-submit token. A random value is set in a readable cookie and
  must be echoed in the X-CSRF-Token header on every state-changing request.

Environment: JWT_SECRET (required in production), ACCESS_TOKEN_MINUTES (15),
REFRESH_TOKEN_DAYS (7), COOKIE_SECURE (1).
"""

from __future__ import annotations

import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
import structlog
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Response

logger = structlog.get_logger(__name__)

ACCESS_COOKIE = "fraudsim_access"
REFRESH_COOKIE = "fraudsim_refresh"
CSRF_COOKIE = "fraudsim_csrf"
CSRF_HEADER = "x-csrf-token"
REFRESH_PATH = "/api/v1/auth"
ALGORITHM = "HS256"

_hasher = PasswordHasher()
_dev_secret = secrets.token_urlsafe(48)
_warned = False

TokenType = Literal["access", "refresh"]


def jwt_secret() -> str:
    global _warned
    secret = os.environ.get("JWT_SECRET")
    if secret:
        return secret
    if not _warned:
        logger.warning("JWT_SECRET is not set: using a random per-process secret (dev only)")
        _warned = True
    return _dev_secret


def access_ttl() -> timedelta:
    return timedelta(minutes=float(os.environ.get("ACCESS_TOKEN_MINUTES", "15")))


def refresh_ttl() -> timedelta:
    return timedelta(days=float(os.environ.get("REFRESH_TOKEN_DAYS", "7")))


def cookie_secure() -> bool:
    return os.environ.get("COOKIE_SECURE", "1") not in ("0", "false", "False")


# ─── Passwords ────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        # Spend comparable time so unknown users are not distinguishable by timing.
        _hasher.hash(password)
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# ─── Tokens ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    role: str
    token_version: int
    token_type: TokenType
    expires_at: datetime


def create_token(
    user_id: int, role: str, token_version: int, token_type: TokenType, now: datetime | None = None
) -> tuple[str, datetime]:
    now = now or datetime.now(UTC)
    exp = now + (access_ttl() if token_type == "access" else refresh_ttl())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "tv": token_version,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM), exp


class TokenError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def decode_token(token: str, expected: TokenType) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            jwt_secret(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp", "iat", "typ", "tv"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token_expired", "Session expired; sign in again") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid_token", "Invalid session token") from exc
    if payload.get("typ") != expected:
        raise TokenError("invalid_token", "Wrong token type")
    return TokenClaims(
        user_id=int(payload["sub"]),
        role=str(payload.get("role", "")),
        token_version=int(payload["tv"]),
        token_type=expected,
        expires_at=datetime.fromtimestamp(int(payload["exp"]), UTC),
    )


# ─── Cookies ──────────────────────────────────────────────────────────


def set_session_cookies(response: Response, user_id: int, role: str, token_version: int) -> None:
    access, _ = create_token(user_id, role, token_version, "access")
    refresh, _ = create_token(user_id, role, token_version, "refresh")
    secure = cookie_secure()
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=int(access_ttl().total_seconds()),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=REFRESH_PATH,
        max_age=int(refresh_ttl().total_seconds()),
    )


def clear_session_cookies(response: Response) -> None:
    secure = cookie_secure()
    response.delete_cookie(ACCESS_COOKIE, path="/", secure=secure, httponly=True, samesite="lax")
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_PATH, secure=secure, httponly=True, samesite="lax"
    )


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str) -> None:
    # Readable by the page's script (not httpOnly): the double-submit pattern.
    response.set_cookie(
        CSRF_COOKIE, token, httponly=False, secure=cookie_secure(), samesite="lax", path="/"
    )
