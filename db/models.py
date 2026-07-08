"""SQLAlchemy declarative models.

`usage_counters` (PR3) lands in a later Phase C PR.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("provider", "provider_sub", name="uq_users_provider_sub"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(unique=True)
    provider: Mapped[str]
    provider_sub: Mapped[str]
    display_name: Mapped[str | None] = mapped_column(default=None)
    avatar_url: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Conversation(Base):
    """Source of truth for conversation history (docs/api/memory.md).
    Qdrant is a derived semantic index referencing rows here via
    qdrant_point_id, not a co-equal store."""

    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str]
    content: Mapped[str]
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
