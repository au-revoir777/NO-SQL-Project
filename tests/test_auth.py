"""
Phase 2, P2: authentication, roles, CSRF, rate limiting and the audit trail.

Users live in a temporary database. Every password and the JWT secret are
generated at random per test session, so no credential-like literal is committed.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from fraudsim import appdb
from fraudsim.api.main import app
from fraudsim.api.v1.auth import audit
from fraudsim.api.v1.auth.ratelimit import limiter
from fraudsim.api.v1.auth.security import ACCESS_COOKIE, CSRF_COOKIE, create_token
from fraudsim.api.v1.auth.users import create_user, seed_demo_users
from fraudsim.appdb.models import Role
from fraudsim.cli import main as cli


def random_password() -> str:
    return secrets.token_urlsafe(18)


ADMIN = ("admin@example.test", random_password())
ANALYST = ("analyst@example.test", random_password())
WRONG = random_password()


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("APP_AUDIT_DIR", str(tmp_path / "app_audit"))
    monkeypatch.delenv("REDIS_URL", raising=False)
    for k in (
        "DEMO_ADMIN_EMAIL",
        "DEMO_ADMIN_PASSWORD",
        "DEMO_ANALYST_EMAIL",
        "DEMO_ANALYST_PASSWORD",
    ):
        monkeypatch.delenv(k, raising=False)
    appdb.upgrade(url)
    db = next(appdb.session_scope(url))
    create_user(db, *ADMIN, Role.ADMIN)
    create_user(db, *ANALYST, Role.ANALYST)
    db.close()
    limiter().reset()
    yield url
    limiter().reset()


@pytest.fixture
def client(env: str) -> TestClient:
    # https base URL: the session cookies are Secure.
    return TestClient(app, base_url="https://testserver")


def csrf(c: TestClient) -> str:
    return c.get("/api/v1/auth/csrf").json()["csrf_token"]


def login(c: TestClient, email: str, password: str):  # type: ignore[no-untyped-def]
    token = csrf(c)
    return c.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": token},
    )


def headers(c: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": c.cookies.get(CSRF_COOKIE) or ""}


# ─── Login ────────────────────────────────────────────────────────────


def test_login_sets_hardened_cookies_and_me_works(client: TestClient) -> None:
    resp = login(client, *ANALYST)
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["role"] == "analyst"
    set_cookies = resp.headers.get_list("set-cookie")
    access = next(h for h in set_cookies if h.startswith(ACCESS_COOKIE))
    refresh = next(h for h in set_cookies if h.startswith("fraudsim_refresh"))
    for cookie in (access, refresh):
        low = cookie.lower()
        assert "httponly" in low and "secure" in low and "samesite=lax" in low
    assert "path=/api/v1/auth" in refresh.lower()
    me = client.get("/api/v1/auth/me").json()
    assert me["user"]["email"] == ANALYST[0]
    assert "password" not in str(me)


def test_wrong_password_and_unknown_user_get_the_same_answer(client: TestClient) -> None:
    wrong = login(client, ANALYST[0], WRONG)
    unknown = login(client, "nobody@example.test", WRONG)
    for resp in (wrong, unknown):
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_credentials"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_rate_limit_locks_out_after_repeated_failures(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGIN_MAX_FAILURES", "3")
    for _ in range(3):
        assert login(client, ANALYST[0], WRONG).status_code == 401
    locked = login(client, *ANALYST)  # even the right password is refused now
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "rate_limited"
    assert int(locked.headers["retry-after"]) > 0
    actions = [e.action_type for e in audit.trail().read_entries()]
    assert actions.count("LOGIN_FAILED") == 3 and "LOGIN_RATE_LIMITED" in actions


def test_inactive_user_cannot_log_in(client: TestClient, env: str) -> None:
    from fraudsim.api.v1.auth.users import find_by_email

    db = next(appdb.session_scope(env))
    user = find_by_email(db, ANALYST[0])
    assert user is not None
    user.is_active = False
    db.commit()
    db.close()
    assert login(client, *ANALYST).status_code == 401


# ─── Tokens ───────────────────────────────────────────────────────────


def test_expired_token_is_rejected(client: TestClient) -> None:
    login(client, *ANALYST)
    me = client.get("/api/v1/auth/me").json()["user"]
    old, _ = create_token(
        me["id"], "analyst", 0, "access", now=datetime.now(UTC) - timedelta(hours=2)
    )
    client.cookies.set(ACCESS_COOKIE, old, domain="testserver.local", path="/")
    fresh = TestClient(app, base_url="https://testserver")
    fresh.cookies.set(ACCESS_COOKIE, old)
    resp = fresh.get("/api/v1/auth/me")
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "token_expired"


def test_tampered_and_wrong_type_tokens_are_rejected(client: TestClient) -> None:
    login(client, *ADMIN)
    me = client.get("/api/v1/auth/me").json()["user"]
    refresh_as_access, _ = create_token(me["id"], "admin", 0, "refresh")
    c = TestClient(app, base_url="https://testserver")
    c.cookies.set(ACCESS_COOKIE, refresh_as_access)
    assert c.get("/api/v1/auth/me").json()["error"]["code"] == "invalid_token"
    c.cookies.set(ACCESS_COOKIE, refresh_as_access[:-4] + "AAAA")
    assert c.get("/api/v1/auth/me").status_code == 401


def test_refresh_issues_a_new_session(client: TestClient) -> None:
    login(client, *ANALYST)
    resp = client.post("/api/v1/auth/refresh", headers=headers(client))
    assert resp.status_code == 200 and resp.json()["user"]["email"] == ANALYST[0]


def test_logout_revokes_existing_tokens(client: TestClient) -> None:
    login(client, *ANALYST)
    stolen = client.cookies.get(ACCESS_COOKIE)
    assert client.post("/api/v1/auth/logout", headers=headers(client)).status_code == 204
    replay = TestClient(app, base_url="https://testserver")
    replay.cookies.set(ACCESS_COOKIE, stolen or "")
    resp = replay.get("/api/v1/auth/me")
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "session_revoked"


# ─── CSRF ─────────────────────────────────────────────────────────────


def test_csrf_is_required_on_state_changing_requests(client: TestClient) -> None:
    no_header = client.post(
        "/api/v1/auth/login", json={"email": ANALYST[0], "password": ANALYST[1]}
    )
    assert no_header.status_code == 403 and no_header.json()["error"]["code"] == "csrf_failed"
    login(client, *ADMIN)
    bad = {"X-CSRF-Token": secrets.token_urlsafe(16)}  # never the cookie value
    for method, path, body in (
        ("POST", "/api/v1/auth/logout", None),
        ("POST", "/api/v1/admin/users", {"email": "x@example.test", "password": "x" * 12}),
        ("PATCH", "/api/v1/admin/users/1", {"display_name": "x"}),
    ):
        for hdrs in ({}, bad):
            resp = client.request(method, path, json=body, headers=hdrs)
            assert resp.status_code == 403, (method, path)
            assert resp.json()["error"]["code"] == "csrf_failed"


# ─── Role checks, over the whole router ───────────────────────────────


def _v1_routes(prefixes: tuple[str, ...]) -> list[tuple[str, str]]:
    out = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith(prefixes):
            for method in sorted(route.methods - {"HEAD"}):
                out.append((method, route.path.replace("{user_id}", "1")))
    return out


ADMIN_ROUTES = _v1_routes(("/api/v1/admin", "/api/v1/rules"))
PUBLIC = {"/api/v1/health", "/api/v1/auth/csrf", "/api/v1/auth/login", "/api/v1/auth/refresh"}
PROTECTED_ROUTES = [r for r in _v1_routes(("/api/v1",)) if r[1] not in PUBLIC]


def test_admin_route_list_is_not_empty() -> None:
    assert len(ADMIN_ROUTES) >= 4  # list, create, update users; rules


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_analyst_is_forbidden_from_every_admin_endpoint(
    client: TestClient, method: str, path: str
) -> None:
    login(client, *ANALYST)
    resp = client.request(method, path, json={}, headers=headers(client))
    assert resp.status_code == 403, (method, path, resp.text)
    assert resp.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize(("method", "path"), PROTECTED_ROUTES)
def test_anonymous_requests_are_rejected(client: TestClient, method: str, path: str) -> None:
    resp = client.request(method, path, json={}, headers={"X-CSRF-Token": "x"})
    assert resp.status_code == 401, (method, path, resp.text)


def test_planned_routers_answer_501_when_signed_in(client: TestClient) -> None:
    login(client, *ADMIN)
    for name in (
        "alerts",
        "cases",
        "entities",
        "graph",
        "reports",
        "experiments",
        "rules",
        "stream",
    ):
        resp = client.get(f"/api/v1/{name}")
        assert resp.status_code == 501 and "milestone P" in resp.json()["error"]["message"]


# ─── User administration ──────────────────────────────────────────────


def test_admin_manages_users_without_deleting(client: TestClient) -> None:
    login(client, *ADMIN)
    new_password = random_password()
    h = headers(client)
    created = client.post(
        "/api/v1/admin/users",
        json={
            "email": "New.Person@Example.test",
            "password": new_password,
            "role": "analyst",
        },
        headers=h,
    )
    assert created.status_code == 201 and created.json()["email"] == "new.person@example.test"
    uid = created.json()["id"]
    dup = client.post(
        "/api/v1/admin/users",
        json={"email": "new.person@example.test", "password": random_password()},
        headers=h,
    )
    assert dup.status_code == 409
    short = client.post(
        "/api/v1/admin/users", json={"email": "s@example.test", "password": "short"}, headers=h
    )
    assert short.status_code == 422

    # The new user signs in; promoting them revokes their current session.
    other = TestClient(app, base_url="https://testserver")
    assert login(other, "new.person@example.test", new_password).status_code == 200
    up = client.patch(f"/api/v1/admin/users/{uid}", json={"role": "admin"}, headers=h)
    assert up.status_code == 200 and up.json()["role"] == "admin"
    assert other.get("/api/v1/auth/me").status_code == 401

    off = client.patch(f"/api/v1/admin/users/{uid}", json={"is_active": False}, headers=h)
    assert off.json()["is_active"] is False
    assert login(other, "new.person@example.test", new_password).status_code == 401
    page = client.get("/api/v1/admin/users").json()
    assert page["total"] == 3 and {u["email"] for u in page["items"]} >= {"new.person@example.test"}

    me = client.get("/api/v1/auth/me").json()["user"]
    self_off = client.patch(f"/api/v1/admin/users/{me['id']}", json={"is_active": False}, headers=h)
    assert self_off.status_code == 409
    assert (
        client.patch("/api/v1/admin/users/999", json={"role": "admin"}, headers=h).status_code
        == 404
    )


# ─── Audit ────────────────────────────────────────────────────────────


def test_auth_events_are_audited_and_the_chain_verifies(client: TestClient, env: str) -> None:
    login(client, ANALYST[0], WRONG)
    login(client, *ADMIN)
    client.post(
        "/api/v1/admin/users",
        json={"email": "audited@example.test", "password": random_password()},
        headers=headers(client),
    )
    client.post("/api/v1/auth/logout", headers=headers(client))
    entries = audit.trail().read_entries()
    assert [e.action_type for e in entries] == ["LOGIN_FAILED", "LOGIN", "USER_CREATED", "LOGOUT"]
    assert entries[2].actor == ADMIN[0]
    ok, problem = audit.trail().verify()
    assert ok, problem
    assert "password" not in (Path(audit.audit_dir()) / "audit.jsonl").read_text(encoding="utf-8")

    from sqlalchemy import select

    from fraudsim.appdb.models import AuditRef

    db = next(appdb.session_scope(env))
    refs = db.scalars(select(AuditRef)).all()
    db.close()
    assert [r.entry_hash for r in refs] == [e.hash for e in entries]


# ─── Demo users and CLI ───────────────────────────────────────────────


def test_demo_users_come_only_from_env(env: str, monkeypatch: pytest.MonkeyPatch) -> None:
    db = next(appdb.session_scope(env))
    assert seed_demo_users(db) == []  # nothing configured, nothing created
    monkeypatch.setenv("DEMO_ANALYST_EMAIL", "demo.analyst@example.test")
    monkeypatch.setenv("DEMO_ANALYST_PASSWORD", random_password())
    assert seed_demo_users(db) == ["demo.analyst@example.test"]
    assert seed_demo_users(db) == []  # idempotent
    db.close()


def test_cli_create_user(env: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEW_ADMIN_PW", random_password())
    result = CliRunner().invoke(
        cli,
        [
            "create-user",
            "--email",
            "cli@example.test",
            "--role",
            "admin",
            "--password-env",
            "NEW_ADMIN_PW",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "created admin cli@example.test" in result.output
    again = CliRunner().invoke(
        cli, ["create-user", "--email", "cli@example.test", "--password-env", "NEW_ADMIN_PW"]
    )
    assert again.exit_code != 0 and "already exists" in again.output


def test_redis_limiter_shares_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    import fakeredis
    import redis

    from fraudsim.api.v1.auth.ratelimit import RedisLimiter

    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        redis.Redis,
        "from_url",
        classmethod(lambda cls, url, **kw: fakeredis.FakeRedis(server=server)),
    )
    monkeypatch.setenv("LOGIN_MAX_FAILURES", "2")
    a, b = RedisLimiter("redis://x"), RedisLimiter("redis://x")  # two API processes
    a.fail("email:z@example.test")
    assert b.retry_after("email:z@example.test") == 0
    b.fail("email:z@example.test")
    assert 0 < a.retry_after("email:z@example.test") <= 900
    a.clear("email:z@example.test")
    assert b.retry_after("email:z@example.test") == 0
