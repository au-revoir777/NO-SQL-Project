"""/api/v1/admin: user management (admin only). Users are deactivated, never deleted.

Handlers that use the database or hash passwords are plain `def`: FastAPI runs
them in its threadpool, so argon2 and SQLite never block the event loop.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

from fraudsim.api.v1.auth import audit
from fraudsim.api.v1.auth.deps import DB, AdminUser, client_ip
from fraudsim.api.v1.auth.users import UserError, create_user
from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope, Page
from fraudsim.api.v1.schemas.auth import CreateUserRequest, UpdateUserRequest, UserOut
from fraudsim.appdb.models import Role, User

router = APIRouter(prefix="/admin", tags=["admin"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope, "description": "Not signed in"},
    403: {"model": ErrorEnvelope, "description": "Admin role required, or CSRF check failed"},
}


@router.get(
    "/users", response_model=Page[UserOut], operation_id="admin_list_users", responses=ERRORS
)
def list_users(
    admin: AdminUser,
    db: DB,
    cursor: int = Query(default=0, ge=0, description="Offset returned as next_cursor"),
    limit: int = Query(default=50, ge=1, le=200),
) -> Page[UserOut]:
    total = int(db.scalar(select(func.count()).select_from(User)) or 0)
    rows = db.scalars(select(User).order_by(User.id).offset(cursor).limit(limit)).all()
    nxt = cursor + len(rows)
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in rows],
        next_cursor=str(nxt) if nxt < total else None,
        total=total,
    )


@router.post(
    "/users",
    response_model=UserOut,
    status_code=201,
    operation_id="admin_create_user",
    responses={**ERRORS, 409: {"model": ErrorEnvelope, "description": "Email already in use"}},
)
def create(body: CreateUserRequest, admin: AdminUser, request: Request, db: DB) -> UserOut:
    try:
        user = create_user(db, body.email, body.password, Role(body.role), body.display_name)
    except UserError as exc:
        status = 409 if "already exists" in str(exc) else 422
        raise ApiError(
            status, "conflict" if status == 409 else "validation_error", str(exc)
        ) from exc
    audit.record(
        "USER_CREATED",
        admin.email,
        "user",
        str(user.id),
        {"email": user.email, "role": user.role.value, "ip": client_ip(request)},
        db,
    )
    return UserOut.model_validate(user)


@router.patch(
    "/users/{user_id}",
    response_model=UserOut,
    operation_id="admin_update_user",
    responses={**ERRORS, 404: {"model": ErrorEnvelope, "description": "No such user"}},
)
def update(
    user_id: int, body: UpdateUserRequest, admin: AdminUser, request: Request, db: DB
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found", f"No user with id {user_id}")
    changes: dict[str, object] = {}
    if body.role is not None and body.role != user.role.value:
        if user.id == admin.id:
            raise ApiError(409, "conflict", "You cannot change your own role")
        changes["role"] = [user.role.value, body.role]
        user.role = Role(body.role)
    if body.is_active is not None and body.is_active != user.is_active:
        if user.id == admin.id and not body.is_active:
            raise ApiError(409, "conflict", "You cannot deactivate your own account")
        changes["is_active"] = [user.is_active, body.is_active]
        user.is_active = body.is_active
    if body.display_name is not None and body.display_name != user.display_name:
        changes["display_name"] = [user.display_name, body.display_name]
        user.display_name = body.display_name
    if "role" in changes or "is_active" in changes:
        user.token_version += 1  # existing sessions must re-authenticate with the new rights
    db.commit()
    if changes:
        audit.record(
            "USER_UPDATED",
            admin.email,
            "user",
            str(user.id),
            {"changes": changes, "ip": client_ip(request)},
            db,
        )
    db.refresh(user)
    return UserOut.model_validate(user)
