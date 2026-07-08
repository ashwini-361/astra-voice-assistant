import uuid

from memory import memory_manager


class _FakeStore:
    def __init__(self, dim=None) -> None:  # pylint: disable=unused-argument
        self.items = []

    def upsert(self, doc_id, embedding, content, user_id):  # pylint: disable=unused-argument
        self.items.append((content, user_id))
        return str(uuid.uuid4())

    def search(self, embedding, user_id, top_k=3):  # pylint: disable=unused-argument
        return [content for content, uid in self.items if uid == user_id][:top_k]


class _FakeRow:
    def __init__(self, user_id, role, content):
        self.id = uuid.uuid4()
        self.user_id = user_id
        self.role = role
        self.content = content
        self.qdrant_point_id = None


class _FakeSession:
    def __init__(self, *args, **kwargs):  # pylint: disable=unused-argument
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def add(self, row):  # pylint: disable=unused-argument
        pass

    def commit(self):
        pass

    def refresh(self, row):  # pylint: disable=unused-argument
        pass


def test_memory_retrieval(monkeypatch):
    monkeypatch.setattr(memory_manager, "embed", lambda text: [0.1, 0.2, 0.3])
    monkeypatch.setattr(memory_manager, "VectorStore", _FakeStore)
    monkeypatch.setattr(memory_manager, "Conversation", _FakeRow)
    monkeypatch.setattr(memory_manager, "Session", _FakeSession)
    monkeypatch.setattr(memory_manager, "get_sync_engine", lambda: None)

    manager = memory_manager.MemoryManager()
    manager.add_interaction("user likes pizza", "assistant suggests toppings", user_id="user-a")
    manager.add_interaction("user asks about weather", "assistant gives forecast", user_id="user-a")

    results = manager.retrieve("pizza", user_id="user-a")
    formatted = manager.format_memories(results)

    assert results
    assert formatted


def test_memory_isolation_between_users(monkeypatch):
    monkeypatch.setattr(memory_manager, "embed", lambda text: [0.1, 0.2, 0.3])
    monkeypatch.setattr(memory_manager, "VectorStore", _FakeStore)
    monkeypatch.setattr(memory_manager, "Conversation", _FakeRow)
    monkeypatch.setattr(memory_manager, "Session", _FakeSession)
    monkeypatch.setattr(memory_manager, "get_sync_engine", lambda: None)

    manager = memory_manager.MemoryManager()
    manager.add_interaction("account A secret", "account A response", user_id="user-a")
    manager.add_interaction("account B secret", "account B response", user_id="user-b")

    results_a = manager.retrieve("secret", user_id="user-a", top_k=10)
    results_b = manager.retrieve("secret", user_id="user-b", top_k=10)

    assert any("account A" in r for r in results_a)
    assert not any("account B" in r for r in results_a)
    assert any("account B" in r for r in results_b)
    assert not any("account A" in r for r in results_b)
