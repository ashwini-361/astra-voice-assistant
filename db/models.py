"""SQLAlchemy declarative models.

PR1A adds no tables yet -- this module exists so Alembic has a metadata
target to autogenerate/verify against. `users` lands in PR1B,
`conversations` in PR2, `usage_counters` in PR3.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
