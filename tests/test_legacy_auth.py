"""
R1 (M0 audit): the original API routes, the /ws stream and CORS are protected
like /api/v1. Routes are enumerated from the app, so a new unprotected route
fails this test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from auth_fixtures import setup_app_db, sign_in
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from fraudsim.api.main import app
from fraudsim.api.v1.auth.websocket import WS_UNAUTHENTICATED

PUBLIC = {"/health", "/"}
ADMIN_ONLY = {("POST", "/config"), ("POST", "/detectors/{detector_type}")}


def legacy_routes() -> list[tuple[str, str]]:
    out = []
    for r in app.routes:
        if not isinstance(r, APIRoute) or r.path.startswith("/api/v1") or r.path in PUBLIC:
            continue
        if (
            r.path in ("/openapi.json",)
            or r.path.startswith("/docs")
            or r.path.startswith("/redoc")
        ):
            continue
        for m in sorted(r.methods - {"HEAD"}):
            out.append((m, r.path))
    return sorted(out)


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x", path)


@pytest.fixture
def users(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, tuple[str, str]]:
    monkeypatch.setenv("FRAUDSIM_RUNS_DIR", str(tmp_path / "runs"))
    return setup_app_db(tmp_path, monkeypatch)


def client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def test_route_list_covers_the_original_api() -> None:
    routes = legacy_routes()
    assert ("POST", "/runs/start") in routes and ("GET", "/oracle") in routes
    assert len(routes) == 22


@pytest.mark.parametrize(("method", "path"), legacy_routes())
def test_anonymous_requests_are_refused(users: dict, method: str, path: str) -> None:
    resp = client().request(method, concrete(path), json={})
    assert resp.status_code == 401, (method, path, resp.text)
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_health_stays_public(users: dict) -> None:
    assert client().get("/health").status_code == 200


@pytest.mark.parametrize(("method", "path"), sorted(ADMIN_ONLY))
def test_analyst_cannot_change_live_detector_config(users: dict, method: str, path: str) -> None:
    c = client()
    sign_in(c, *users["analyst"])
    resp = c.request(method, concrete(path), json={"enabled": False})
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "forbidden"


def test_posts_need_the_csrf_header(users: dict) -> None:
    c = client()
    sign_in(c, *users["analyst"])
    del c.headers["X-CSRF-Token"]
    resp = c.post("/runs/stop")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "csrf_failed"
    c.headers["X-CSRF-Token"] = c.cookies.get("fraudsim_csrf") or ""
    assert c.post("/runs/stop").status_code == 200


def test_analyst_can_read_the_live_api(users: dict) -> None:
    c = client()
    sign_in(c, *users["analyst"])
    assert c.get("/status").status_code == 200
    assert c.get("/scenarios").status_code == 200


def test_websocket_requires_a_session(users: dict) -> None:
    with client().websocket_connect("/ws") as ws, pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_json()
    assert exc.value.code == WS_UNAUTHENTICATED


def test_websocket_refuses_foreign_origins(users: dict) -> None:
    c = client()
    sign_in(c, *users["analyst"])
    with (
        pytest.raises(WebSocketDisconnect),
        c.websocket_connect("/ws", headers={"origin": "https://evil.example"}),
    ):
        pass


def test_websocket_streams_to_a_signed_in_user(users: dict) -> None:
    c = client()
    sign_in(c, *users["analyst"])
    # The test client does not send Secure cookies on its ws:// handshake; a
    # browser does (wss://, or localhost), so pass the session cookie explicitly.
    cookie = f"fraudsim_access={c.cookies.get('fraudsim_access')}"
    with c.websocket_connect(
        "/ws", headers={"origin": "https://testserver", "cookie": cookie}
    ) as ws:
        assert ws.receive_json()["type"] == "INIT_STATE"


def test_cors_allows_only_configured_origins(users: dict) -> None:
    c = client()
    ok = c.options(
        "/status",
        headers={"origin": "http://localhost:3000", "access-control-request-method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = c.options(
        "/status",
        headers={"origin": "https://evil.example", "access-control-request-method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers
