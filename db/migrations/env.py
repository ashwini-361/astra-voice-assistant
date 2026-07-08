"""Alembic environment.

Runs migrations synchronously via psycopg2 -- the app itself uses the
async engine (db/session.py's get_engine/get_sessionmaker) for
request-time access; Alembic only needs a sync connection to apply DDL.
Online mode reuses db/session.py's get_sync_engine() (the same one
memory/memory_manager.py and core/quota.py use) rather than constructing
a second, independently-configured sync engine.
"""
from logging.config import fileConfig

from alembic import context

from core.config import get_settings
from db.models import Base
from db.session import get_sync_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # Offline mode emits literal SQL without a live connection, so it
    # needs a URL string rather than get_sync_engine()'s Engine object.
    dsn = get_settings().postgres_dsn.replace("+asyncpg", "+psycopg2")
    context.configure(
        url=dsn,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = get_sync_engine()
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
