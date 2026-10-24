"""
Phase 2, P1: the /api/v1 contract (error envelope, request ids, health),
the app-state store's migrations, and the committed OpenAPI document.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from auth_fixtures import setup_app_db, sign_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from fraudsim import appdb
from fraudsim.api.main import app
from fraudsim.api.openapi import openapi_dict
from fraudsim.api.v1 import errors

ROOT = Path(__file__).resolve().parents[1]
HEAD = "0003"  # latest Alembic revision
TABLES = {
    "users",
    "cases",
    "case_alerts",
    "notes",
    "labels",
    "rule_sets",
    "reports",
    "audit_refs",
    "alerts",
    "saved_views",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ─── Request ids ──────────────────────────────────────────────────────


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    generated = client.get("/api/v1/runs/current").headers["x-request-id"]
    assert len(generated) == 32
    echoed = client.get("/api/v1/runs/current", headers={"X-Request-ID": "trace-42"})
    assert echoed.headers["x-request-id"] == "trace-42"
    # Unsafe values are replaced, not reflected.
    bad = client.get("/api/v1/runs/current", headers={"X-Request-ID": "x" * 300})
    assert bad.headers["x-request-id"] != "x" * 300


def test_old_routes_also_carry_a_request_id(client: TestClient) -> None:
    assert client.get("/health").headers["x-request-id"]


# ─── Error envelope ───────────────────────────────────────────────────


def _assert_envelope(resp, status: int, code: str) -> dict:  # type: ignore[no-untyped-def]
    assert resp.status_code == status
    body = resp.json()
    assert set(body) == {"error"}
    err = body["error"]
    assert err["code"] == code and err["message"]
    assert err["request_id"] == resp.headers["x-request-id"]
    return err


def test_unknown_v1_path_is_an_enveloped_404(client: TestClient) -> None:
    _assert_envelope(client.get("/api/v1/does-not-exist"), 404, "not_found")


def test_wrong_method_is_an_enveloped_405(client: TestClient) -> None:
    _assert_envelope(client.delete("/api/v1/health"), 405, "method_not_allowed")


@pytest.mark.parametrize(
    "path",
    [
        "entities/search?q=u",
        "graph/neighbourhood?seed=user:u01",
        "reports?limit=1",
        "experiments",
        "rules",
    ],
)
def test_routers_require_sign_in(client: TestClient, path: str) -> None:
    # Signed-in behaviour (501 naming the milestone) is covered in test_auth.py.
    _assert_envelope(client.get(f"/api/v1/{path}"), 401, "unauthenticated")


def test_validation_and_internal_errors_are_enveloped() -> None:
    probe = FastAPI()
    errors.install(probe)

    @probe.get("/api/v1/probe/{n}")
    async def typed(n: int) -> dict[str, int]:
        return {"n": n}

    @probe.get("/api/v1/boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")

    c = TestClient(probe, raise_server_exceptions=False)
    err = _assert_envelope(c.get("/api/v1/probe/abc"), 422, "validation_error")
    assert err["details"][0]["loc"] == ["path", "n"]
    resp = c.get("/api/v1/boom")
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "internal_error"
    assert "secret" not in resp.text  # internals never leak


def test_old_routes_keep_their_error_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    users = setup_app_db(tmp_path, monkeypatch)
    client = TestClient(app, base_url="https://testserver")
    sign_in(client, *users["analyst"])
    resp = client.get("/rings/not-a-ring")
    assert resp.status_code == 404 and "detail" in resp.json()


# ─── App-state store ──────────────────────────────────────────────────


def test_upgrade_creates_the_database_folder(tmp_path: Path) -> None:
    # Regression: a fresh container has no runs/ folder; Alembic's own engine
    # could not create the SQLite file there ("unable to open database file").
    url = f"sqlite:///{(tmp_path / 'not' / 'yet' / 'app.db').as_posix()}"
    appdb.upgrade(url)
    assert appdb.current_revision(url) is not None


def test_migration_round_trip_on_sqlite(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    appdb.upgrade(url)
    engine = create_engine(url)
    assert set(inspect(engine).get_table_names()) >= TABLES
    assert appdb.current_revision(url) == HEAD
    appdb.downgrade(url, "base")
    assert set(inspect(engine).get_table_names()) - {"alembic_version"} == set()
    appdb.upgrade(url)  # and back up again
    assert set(inspect(engine).get_table_names()) >= TABLES
    engine.dispose()


def test_models_match_the_migration(tmp_path: Path) -> None:
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from fraudsim.appdb.models import Base

    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    appdb.upgrade(url)
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == [], diff  # a model change without a migration fails here


def test_health_reports_a_migrated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.delenv("REDIS_URL", raising=False)
    c = TestClient(app)
    before = {x["name"]: x for x in c.get("/api/v1/health").json()["components"]}
    assert before["app_db"]["status"] == "unavailable"
    appdb.upgrade(url)
    body = c.get("/api/v1/health").json()
    comps = {x["name"]: x["status"] for x in body["components"]}
    assert comps["app_db"] == "ok" and comps["api"] == "ok" and comps["redis"] == "not_configured"
    assert body["db_revision"] == HEAD and body["status"] == "ok"


# ─── Contract ─────────────────────────────────────────────────────────


def test_committed_openapi_matches_the_app() -> None:
    committed = json.loads((ROOT / "docs" / "api" / "openapi.json").read_text(encoding="utf-8"))
    assert committed == openapi_dict(), "run `make openapi` and commit docs/api/openapi.json"


def test_v1_routes_document_the_error_envelope() -> None:
    spec = openapi_dict()
    assert "ErrorEnvelope" in spec["components"]["schemas"]
    for path, ops in spec["paths"].items():
        if path.startswith("/api/v1"):
            for op in ops.values():
                assert "422" in op["responses"] or "501" in op["responses"], (path, op)
