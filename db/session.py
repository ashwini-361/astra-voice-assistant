"""Async SQLAlchemy engine/session factory, shared across services."""
from functools import lru_cache
from typing import AsyncIterator

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
