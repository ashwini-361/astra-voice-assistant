"""SQLAlchemy engine/session factories, shared across services.

Two engines against the same Postgres database, deliberately: the async
(asyncpg) engine below is used by FastAPI request handlers (db/session.py's
own get_db dependency). The sync (psycopg2) engine is used by callers that
are blocking/sync by design -- memory/memory_manager.py (whose own
callers already run it via asyncio.to_thread) and core/quota.py -- rather
than introducing async through them. db/migrations/env.py derives the
same sync DSN independently since Alembic's own machinery needs a DSN
string before any engine here is constructed.
"""
from functools import lru_cache
from typing import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_settings


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    return create_async_engine(settings.postgres_dsn, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields an AsyncSession, closed after the request."""
    async with get_sessionmaker()() as session:
        yield session


@lru_cache(maxsize=1)
def get_sync_engine() -> Engine:
    dsn = get_settings().postgres_dsn.replace("+asyncpg", "+psycopg2")
    return create_engine(dsn, pool_pre_ping=True)
