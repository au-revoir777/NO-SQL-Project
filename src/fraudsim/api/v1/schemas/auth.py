"""Schemas for /api/v1/auth and /api/v1/admin/users."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RoleName = Literal["analyst", "admin"]


class CsrfToken(BaseModel):
    csrf_token: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    role: RoleName
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None

    @field_validator("role", mode="before")
    @classmethod
    def _role_value(cls, v: object) -> object:
        return getattr(v, "value", v)  # the ORM stores a Role enum


class Session(BaseModel):
    user: UserOut
    access_expires_in_s: int


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=1024)
    role: RoleName = "analyst"
    display_name: str = Field(default="", max_length=200)


class UpdateUserRequest(BaseModel):
    """Partial update. Users are deactivated, never deleted."""

    role: RoleName | None = None
    is_active: bool | None = None
    display_name: str | None = Field(default=None, max_length=200)
