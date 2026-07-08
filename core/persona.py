"""Single source of truth for the assistant's identity/persona text.

Loaded from prompts/system_prompt.txt so both the orchestrator (CLI/duplex)
and the LLM service (frontend chat + agent loop) present the same identity
instead of each entry point improvising its own.
"""
from functools import lru_cache
from pathlib import Path

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    try:
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "You are Astra, a helpful AI assistant."
