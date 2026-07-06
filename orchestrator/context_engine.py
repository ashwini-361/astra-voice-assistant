"""Context assembly for LLM prompts with deterministic formatting."""
from typing import Optional

from core.persona import load_system_prompt
from orchestrator.memory_buffer import ConversationBuffer

DEFAULT_MAX_CHARS = 4000


def build_prompt(
    buffer: ConversationBuffer,
    user_input: str,
    emotional_state: str | None = None,
    retrieved_memories: str | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    system_prompt = load_system_prompt()
    history = buffer.get_formatted_history()

    sections = [
        f"System:\n{system_prompt}",
        f"Emotional context:\n{emotional_state or '(neutral)'}",
        f"Retrieved memories:\n{retrieved_memories or '(none)'}",
        "History:" if history else "History: (none)",
    ]
    if history:
        sections.append(history)
    sections.append(f"User:\n{user_input}")

    prompt = "\n\n".join(sections)

    if len(prompt) > max_chars:
        prompt = prompt[-max_chars:]
    return prompt
