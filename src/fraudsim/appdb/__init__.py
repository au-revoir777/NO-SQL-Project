"""
App-state store for the web application (SQLAlchemy 2 + Alembic).

DATABASE_URL selects the database (default sqlite:///runs/app.db); Postgres works
through a postgresql+psycopg URL. Migrations live in fraudsim/appdb/migrations and
run with `fraudsim db-upgrade` (or `alembic upgrade head` from the repo root).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_URL = "sqlite:///runs/app.db"
MIGRATIONS = Path(__file__).resolve().parent / "migrations"

_engines: dict[str, Engine] = {}


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def get_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    if url not in _engines:
        _ensure_sqlite_dir(url)
        kw: dict[str, Any] = {}
        if url.startswith("sqlite"):
            kw["connect_args"] = {"check_same_thread": False}
        _engines[url] = create_engine(url, **kw)
    return _engines[url]


def alembic_config(url: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.set_main_option("sqlalchemy.url", url or database_url())
    return cfg


def _ensure_sqlite_dir(url: str) -> None:
    """SQLite cannot create the database's folder; Alembic opens its own engine too."""
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


def upgrade(url: str | None = None, revision: str = "head") -> None:
    _ensure_sqlite_dir(url or database_url())
    command.upgrade(alembic_config(url), revision)


def downgrade(url: str | None = None, revision: str = "base") -> None:
    command.downgrade(alembic_config(url), revision)


def current_revision(url: str | None = None) -> str | None:
    with get_engine(url).connect() as conn:
        if not inspect(conn).has_table("alembic_version"):
            return None
        row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
        return str(row[0]) if row else None


def ping(url: str | None = None) -> bool:
    try:
        with get_engine(url).connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def open_session(url: str | None = None) -> Session:
    """A session for scripts and start-up code; the caller closes it."""
    return sessionmaker(bind=get_engine(url), expire_on_commit=False)()


def session_scope(url: str | None = None) -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    factory = sessionmaker(bind=get_engine(url), expire_on_commit=False)
    with factory() as session:
        yield session
