"""
Request ids and the uniform error envelope for /api/v1.

Every response carries an X-Request-ID header (taken from the request when the
client sends one, generated otherwise). Errors under /api/v1 are returned as
{"error": {"code", "message", "request_id", "details"}}; the pre-existing routes
keep FastAPI's default {"detail": ...} shape so the M7 dashboard is unaffected.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = structlog.get_logger(__name__)

V1_PREFIX = "/api/v1"
REQUEST_ID_HEADER = "x-request-id"
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

HTTP_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    501: "not_implemented",
}


class ApiError(Exception):
    """Raise inside /api/v1 handlers for an enveloped error response."""

    def __init__(
        self, status: int, code: str, message: str, details: list[dict[str, Any]] | None = None
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


class RequestIdMiddleware:
    """Pure-ASGI middleware (works for HTTP and leaves WebSockets untouched)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(REQUEST_ID_HEADER.encode())
        rid = incoming.decode("latin-1") if incoming else ""
        if not _VALID_ID.match(rid):
            rid = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = rid

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != REQUEST_ID_HEADER.encode()
                ]
                headers.append((REQUEST_ID_HEADER.encode(), rid.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_id)


def request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return str(rid) if rid else uuid.uuid4().hex


def _envelope(
    request: Request, status: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message, "request_id": request_id(request)}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body})


def _is_v1(request: Request) -> bool:
    return request.url.path.startswith(V1_PREFIX)


def install(app: FastAPI) -> None:
    """Add the request-id middleware and the /api/v1-scoped exception handlers."""
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _envelope(request, exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> Any:
        if not _is_v1(request):
            return await http_exception_handler(request, exc)
        code = HTTP_CODES.get(exc.status_code, "http_error")
        return _envelope(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> Any:
        if not _is_v1(request):
            return await request_validation_exception_handler(request, exc)
        details = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        return _envelope(request, 422, "validation_error", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> Any:
        # Never leak internals; the request id ties the response to the server log.
        logger.exception("unhandled error", request_id=request_id(request), path=request.url.path)
        if not _is_v1(request):
            return PlainTextResponse("Internal Server Error", status_code=500)
        return _envelope(request, 500, "internal_error", "Internal server error")
