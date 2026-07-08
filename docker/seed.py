"""Seed Postgres + Qdrant with a few sample memories so a fresh clone has
non-empty retrieval to demonstrate. Run via:
docker compose --profile tools run --rm seed (or `make seed`).

Seeds under the reserved local/service user (core.auth.LOCAL_USER_ID,
same identity the native voice loop and make smoke authenticate as --
see docs/api/auth.md) since conversations.user_id is now a required FK
into users(id). The row itself is guaranteed to already exist by
db/migrations/versions/76936a1ecf9d_seed_reserved_local_user.py (`make
seed` depends on `make migrate`) -- this script just proves the memory
pipeline (Postgres insert -> embed -> Qdrant upsert -> retrieve) works
end-to-end against the composed Postgres+Qdrant containers.
"""
import logging
import sys

from core.auth import LOCAL_USER_ID
from memory.memory_manager import MemoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed")

SAMPLE_INTERACTIONS = [
    ("What's your name?", "I'm Astra, your AI assistant."),
    ("What can you help me with?", "I can chat, answer questions, and use tools like web search."),
    ("Remember I prefer concise answers.", "Got it — I'll keep replies short and to the point."),
]


def main() -> int:
    try:
        manager = MemoryManager()
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Could not initialize MemoryManager (Postgres/Qdrant unreachable?): %s", exc)
        return 1

    for user_text, assistant_text in SAMPLE_INTERACTIONS:
        manager.add_interaction(user_text, assistant_text, user_id=LOCAL_USER_ID)
        logger.info("Seeded: %r -> %r", user_text, assistant_text)

    results = manager.retrieve("what is your name", user_id=LOCAL_USER_ID, top_k=1)
    if not results:
        logger.error("Seed completed but retrieval returned nothing — check Qdrant connectivity.")
        return 1

    logger.info("Retrieval check OK: %s", results[0])
    logger.info("Seed complete: %d sample memories stored.", len(SAMPLE_INTERACTIONS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
