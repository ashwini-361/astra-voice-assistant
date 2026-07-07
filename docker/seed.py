"""Seed Qdrant with a few sample memories so a fresh clone has non-empty
retrieval to demonstrate. Run via: docker compose --profile tools run --rm seed
(or `make seed`).

Deliberately does NOT seed a "test user" — there is no user/auth concept in
the codebase yet (see docs/ASTRA_WEB_SERVICE_PLAN.md Phase W3). This just
proves the memory pipeline (embed -> Qdrant upsert -> retrieve) works
end-to-end against the composed Qdrant container.
"""
import logging
import sys

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
        logger.error("Could not initialize MemoryManager (Qdrant unreachable?): %s", exc)
        return 1

    for user_text, assistant_text in SAMPLE_INTERACTIONS:
        manager.add_interaction(user_text, assistant_text)
        logger.info("Seeded: %r -> %r", user_text, assistant_text)

    results = manager.retrieve("what is your name", top_k=1)
    if not results:
        logger.error("Seed completed but retrieval returned nothing — check Qdrant connectivity.")
        return 1

    logger.info("Retrieval check OK: %s", results[0])
    logger.info("Seed complete: %d sample memories stored.", len(SAMPLE_INTERACTIONS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
