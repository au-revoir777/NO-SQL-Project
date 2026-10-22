"""
Shared set-up for tests that call protected routes: a temporary app database
with one admin and one analyst (random passwords), and a helper that signs a
TestClient in and sends the CSRF header on every request.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fraudsim import appdb
from fraudsim.api.v1.auth.ratelimit import limiter
from fraudsim.api.v1.auth.security import CSRF_COOKIE
from fraudsim.api.v1.auth.users import create_user
from fraudsim.appdb.models import Role

ADMIN_EMAIL = "admin@example.test"
ANALYST_EMAIL = "analyst@example.test"


def setup_app_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, tuple[str, str]]:
    """Migrate a fresh app DB and create the two users; return {role: (email, password)}."""
    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("APP_AUDIT_DIR", str(tmp_path / "app_audit"))
    monkeypatch.delenv("REDIS_URL", raising=False)
    appdb.upgrade(url)
    users = {
        "admin": (ADMIN_EMAIL, secrets.token_urlsafe(18)),
        "analyst": (ANALYST_EMAIL, secrets.token_urlsafe(18)),
    }
    db = appdb.open_session(url)
    create_user(db, *users["admin"], Role.ADMIN)
    create_user(db, *users["analyst"], Role.ANALYST)
    db.close()
    limiter().reset()
    return users


def sign_in(client: TestClient, email: str, password: str) -> None:
    """Log the client in and send the CSRF header on every later request."""
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": token},
    )
    assert resp.status_code == 200, resp.text
    client.headers["X-CSRF-Token"] = client.cookies.get(CSRF_COOKIE) or ""
