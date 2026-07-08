"""Manages long-term memory storage and retrieval.

Postgres `conversations` is the source of truth (docs/api/memory.md);
Qdrant is a derived semantic index referencing rows there by id, not a
co-equal store. Uses a sync (psycopg2) engine, not the app's async
engine (db/session.py) -- MemoryManager's callers
(orchestrator/pipeline.py, services/agent_control/agent_memory.py) are
blocking/sync call sites (the latter already wraps calls in
asyncio.to_thread), matching the existing sync VectorStore/qdrant_client
usage rather than introducing async through them.
"""
import logging
from functools import lru_cache
from typing import List

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.config import get_settings
from db.models import Conversation
from memory.embedding_model import embed
from memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_sync_engine():
    return create_engine(get_settings().postgres_dsn.replace("+asyncpg", "+psycopg2"), pool_pre_ping=True)


class MemoryManager:
    def __init__(self) -> None:
        sample_vector = embed("warmup")
        self.store = VectorStore(dim=len(sample_vector))

    def add_interaction(self, user_text: str, assistant_text: str, user_id: str) -> None:
        """Postgres is the source of truth: both turns are inserted as rows.
        Only assistant_text is embedded+indexed in Qdrant (docs/api/memory.md),
        with the Qdrant point id written back onto that row afterward."""
        with Session(_get_sync_engine()) as session:
            session.add(Conversation(user_id=user_id, role="user", content=user_text))
            assistant_row = Conversation(user_id=user_id, role="assistant", content=assistant_text)
            session.add(assistant_row)
            session.commit()
            session.refresh(assistant_row)
            doc_id = str(assistant_row.id)

            vector = embed(assistant_text)
            point_id = self.store.upsert(doc_id, vector, assistant_text, user_id=user_id)

            assistant_row.qdrant_point_id = point_id
            session.commit()

        logger.info("Stored memory %s", doc_id)

    def retrieve(self, query: str, user_id: str, top_k: int = 3) -> List[str]:
        query_vec = embed(query)
        return self.store.search(query_vec, user_id=user_id, top_k=top_k)

    def format_memories(self, memories: List[str]) -> str:
        if not memories:
            return "(no long-term memories)"
        lines = [f"Memory {idx+1}: {mem}" for idx, mem in enumerate(memories)]
        return "\n".join(lines)
