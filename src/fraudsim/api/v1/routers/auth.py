"""
/api/v1/auth: CSRF token, login, refresh, logout and the current user.

Login and refresh are CSRF-protected too (the client first calls GET /auth/csrf).
Failed logins count against both the email and the client address (rate limit).

Handlers that use the database or hash passwords are plain `def`: FastAPI runs
them in its threadpool, so argon2 and SQLite never block the event loop.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from fraudsim.api.v1.auth import audit
from fraudsim.api.v1.auth.deps import DB, CurrentUser, client_ip, csrf_protect, require_user
from fraudsim.api.v1.auth.ratelimit import limiter
from fraudsim.api.v1.auth.security import (
    REFRESH_COOKIE,
    TokenError,
    access_ttl,
    clear_session_cookies,
    decode_token,
    new_csrf_token,
    set_csrf_cookie,
    set_session_cookies,
    verify_password,
)
from fraudsim.api.v1.auth.users import find_by_email, normalise_email
from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope
from fraudsim.api.v1.schemas.auth import CsrfToken, LoginRequest, Session, UserOut
from fraudsim.appdb.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope, "description": "Not signed in or session invalid"},
    403: {"model": ErrorEnvelope, "description": "CSRF check failed"},
}


def _session(user: User) -> Session:
    return Session(
        user=UserOut.model_validate(user), access_expires_in_s=int(access_ttl().total_seconds())
    )


@router.get("/csrf", response_model=CsrfToken, operation_id="auth_csrf")
async def csrf(response: Response) -> CsrfToken:
    """Issue a CSRF token (also set as a readable cookie) for the double-submit check."""
    token = new_csrf_token()
    set_csrf_cookie(response, token)
    return CsrfToken(csrf_token=token)


@router.post(
    "/login",
    response_model=Session,
    operation_id="auth_login",
    dependencies=[Depends(csrf_protect)],
    responses={
        **ERRORS,
        429: {"model": ErrorEnvelope, "description": "Too many failed attempts"},
    },
)
def login(body: LoginRequest, request: Request, response: Response, db: DB) -> Session:
    email = normalise_email(body.email)
    ip = client_ip(request)
    keys = (f"email:{email}", f"ip:{ip}")
    lim = limiter()
    wait = max(lim.retry_after(k) for k in keys)
    if wait:
        audit.record("LOGIN_RATE_LIMITED", email, "user", email, {"ip": ip}, db)
        raise ApiError(
            429,
            "rate_limited",
            "Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    user = find_by_email(db, email)
    if user is None or not user.is_active or not verify_password(user.password_hash, body.password):
        for k in keys:
            lim.fail(k)
        audit.record("LOGIN_FAILED", email, "user", email, {"ip": ip}, db)
        # One message for every failure: no hint whether the account exists.
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect")
    lim.clear(keys[0])
    user.last_login_at = datetime.now(UTC)
    db.commit()
    set_session_cookies(response, user.id, user.role.value, user.token_version)
    audit.record("LOGIN", user.email, "user", str(user.id), {"ip": ip, "role": user.role.value}, db)
    return _session(user)


@router.post(
    "/refresh",
    response_model=Session,
    operation_id="auth_refresh",
    dependencies=[Depends(csrf_protect)],
    responses=ERRORS,
)
def refresh(request: Request, response: Response, db: DB) -> Session:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise ApiError(401, "unauthenticated", "No refresh session")
    try:
        claims = decode_token(token, "refresh")
    except TokenError as exc:
        raise ApiError(401, exc.code, exc.message) from exc
    user = db.get(User, claims.user_id)
    if user is None or not user.is_active or user.token_version != claims.token_version:
        clear_session_cookies(response)
        raise ApiError(401, "session_revoked", "Session is no longer valid; sign in again")
    set_session_cookies(response, user.id, user.role.value, user.token_version)
    return _session(user)


@router.post(
    "/logout",
    status_code=204,
    response_class=Response,
    response_model=None,
    operation_id="auth_logout",
    dependencies=[Depends(require_user), Depends(csrf_protect)],
    responses=ERRORS,
)
def logout(user: CurrentUser, request: Request, db: DB) -> Response:
    # Revoke every token issued so far for this user, then drop the cookies.
    user.token_version += 1
    db.commit()
    audit.record("LOGOUT", user.email, "user", str(user.id), {"ip": client_ip(request)}, db)
    response = Response(status_code=204)
    clear_session_cookies(response)
    return response


@router.get("/me", response_model=Session, operation_id="auth_me", responses=ERRORS)
async def me(user: CurrentUser) -> Session:
    return _session(user)
