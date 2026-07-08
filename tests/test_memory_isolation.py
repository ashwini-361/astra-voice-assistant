"""Privacy-critical isolation test (docs/api/memory.md): two accounts, each
adding distinct identifiable content, must never see each other's memories
via either the Qdrant-search path or the Postgres conversations read path.

Requires a live Postgres + Qdrant (see docker-compose.yml) -- skips with a
clear reason if unreachable, so `pytest tests -q` still passes on a
machine without the stack running. Runs for real in CI (.github/workflows/
smoke-test.yml already brings up postgres+qdrant before the test step).
"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from db.models import Conversation, User
from db.session import get_sync_engine
from memory.memory_manager import MemoryManager


def _live_postgres_and_qdrant_available() -> bool:
    try:
        engine = get_sync_engine()
        with engine.connect():
            pass
    except Exception:  # pylint: disable=broad-except
        return False
    try:
        from qdrant_client import QdrantClient
        QdrantClient(url=str(get_settings().qdrant_url), timeout=2.0).get_collections()
    except Exception:  # pylint: disable=broad-except
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _live_postgres_and_qdrant_available(),
    reason="requires a live Postgres + Qdrant (docker compose up postgres qdrant)",
)


@pytest.fixture
def two_users():
    """Create two throwaway users for isolation testing, clean up after."""
    engine = get_sync_engine()
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(User(id=user_a_id, email=f"a-{user_a_id}@test.local", provider="local", provider_sub=str(user_a_id)))
        session.add(User(id=user_b_id, email=f"b-{user_b_id}@test.local", provider="local", provider_sub=str(user_b_id)))
        session.commit()

    yield str(user_a_id), str(user_b_id)

    with Session(engine) as session:
        session.query(Conversation).filter(Conversation.user_id.in_([user_a_id, user_b_id])).delete(synchronize_session=False)
        session.query(User).filter(User.id.in_([user_a_id, user_b_id])).delete(synchronize_session=False)
        session.commit()


def test_qdrant_search_does_not_leak_across_users(two_users):
    user_a, user_b = two_users
    manager = MemoryManager()

    manager.add_interaction("what's my bank PIN reminder?", "Account A's secret note: 4471", user_id=user_a)
    manager.add_interaction("what's my bank PIN reminder?", "Account B's secret note: 9902", user_id=user_b)

    results_a = manager.retrieve("secret note", user_id=user_a, top_k=10)
    results_b = manager.retrieve("secret note", user_id=user_b, top_k=10)

    assert any("Account A" in r for r in results_a)
    assert not any("Account B" in r for r in results_a)
    assert any("Account B" in r for r in results_b)
    assert not any("Account A" in r for r in results_b)


def test_postgres_conversations_does_not_leak_across_users(two_users):
    user_a, user_b = two_users
    manager = MemoryManager()

    manager.add_interaction("account A turn", "Account A's private reply", user_id=user_a)
    manager.add_interaction("account B turn", "Account B's private reply", user_id=user_b)

    engine = get_sync_engine()
    with Session(engine) as session:
        rows_a = session.execute(select(Conversation).where(Conversation.user_id == user_a)).scalars().all()
        rows_b = session.execute(select(Conversation).where(Conversation.user_id == user_b)).scalars().all()

    content_a = " ".join(r.content for r in rows_a)
    content_b = " ".join(r.content for r in rows_b)

    assert "Account A" in content_a
    assert "Account B" not in content_a
    assert "Account B" in content_b
    assert "Account A" not in content_b


def test_qdrant_point_deleted_postgres_still_has_authoritative_content(two_users):
    """Postgres is the source of truth (docs/api/memory.md) -- if the
    Qdrant point is lost, the Postgres row must still hold the content."""
    user_a, _ = two_users
    manager = MemoryManager()
    manager.add_interaction("source of truth check", "This must survive a Qdrant point deletion", user_id=user_a)

    engine = get_sync_engine()
    with Session(engine) as session:
        row = session.execute(
            select(Conversation).where(Conversation.user_id == user_a, Conversation.role == "assistant")
        ).scalars().first()
        assert row is not None
        assert row.qdrant_point_id is not None
        point_id = row.qdrant_point_id

    from qdrant_client import QdrantClient
    client = QdrantClient(url=str(get_settings().qdrant_url), timeout=3.0)
    client.delete(collection_name=manager.store.collection_name, points_selector=[str(point_id)])

    with Session(engine) as session:
        row = session.execute(
            select(Conversation).where(Conversation.user_id == user_a, Conversation.role == "assistant")
        ).scalars().first()
        assert row is not None
        assert row.content == "This must survive a Qdrant point deletion"
