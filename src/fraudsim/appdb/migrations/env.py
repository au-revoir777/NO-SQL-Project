"""Alembic environment for the app-state store (fraudsim.appdb)."""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from fraudsim.appdb import database_url
from fraudsim.appdb.models import Base

config = context.config
target_metadata = Base.metadata
url = config.get_main_option("sqlalchemy.url") or database_url()


def run_migrations_offline() -> None:
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": url}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        # Batch mode lets ALTER TABLE migrations work on SQLite too.
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
