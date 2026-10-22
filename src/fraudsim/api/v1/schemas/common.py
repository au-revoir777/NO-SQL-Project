"""Envelopes shared by every /api/v1 route."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str = Field(description="Machine-readable error code, e.g. not_found, validation_error")
    message: str
    request_id: str
    details: list[dict[str, object]] | None = Field(
        default=None, description="Field-level problems for validation errors"
    )


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class Page(BaseModel, Generic[T]):
    """Cursor pagination: pass next_cursor back as ?cursor= to get the next page."""

    items: list[T]
    next_cursor: str | None = None
    total: int | None = Field(default=None, description="Total matching items, when cheap to count")
