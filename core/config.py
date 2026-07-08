from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, Field


class Settings(BaseSettings):
    whisper_host: str = Field(default="0.0.0.0")
    whisper_port: int = Field(default=8001)

    llm_host: str = Field(default="0.0.0.0")
    llm_port: int = Field(default=8002)
    ollama_api_url: AnyHttpUrl = Field(default="http://127.0.0.1:11434")
    llm_model: str = Field(default="qwen2.5:3b")
    llm_provider: str = Field(default="ollama")
    lmstudio_api_url: AnyHttpUrl = Field(default="http://127.0.0.1:1234")
    openai_api_url: AnyHttpUrl = Field(default="https://api.openai.com/v1")
    openai_api_key: str = Field(default="")
    custom_llm_api_url: str = Field(default="")
    custom_llm_api_key: str = Field(default="")
    custom_llm_mode: str = Field(default="openai")

    tts_host: str = Field(default="0.0.0.0")
    tts_port: int = Field(default=8003)
    piper_api_url: AnyHttpUrl = Field(default="http://127.0.0.1:59125")
    piper_voice: str = Field(default="en_US-lessac-medium")
    piper_speaker_id: int | None = Field(default=None)

    intent_host: str = Field(default="0.0.0.0")
    intent_port: int = Field(default=8004)
    intent_model_path: str = Field(default="models/intent.onnx")

    qdrant_url: AnyHttpUrl = Field(default="http://127.0.0.1:6333")

    # Gateway service (auth-only -- see docs/api/gateway.md)
    gateway_host: str = Field(default="0.0.0.0")
    gateway_port: int = Field(default=8000)

    # JWT (stateless access+refresh pair, no sessions/revocation table --
    # see docs/adr/ADR-007-multiuser-pivot.md)
    jwt_secret: str = Field(default="change-me-in-.env")
    jwt_access_expiry_minutes: int = Field(default=30)
    jwt_refresh_expiry_days: int = Field(default=30)

    # OAuth providers (Google/GitHub, per ADR-001)
    oauth_google_client_id: str = Field(default="")
    oauth_google_client_secret: str = Field(default="")
    oauth_github_client_id: str = Field(default="")
    oauth_github_client_secret: str = Field(default="")
    oauth_redirect_base_url: str = Field(default="http://127.0.0.1:8000")

    # Postgres (Phase C PR1A: infra only; users/conversations/usage_counters
    # tables land in PR1B/PR2/PR3 respectively via Alembic)
    postgres_dsn: str = Field(
        default="postgresql+asyncpg://astra:astra@127.0.0.1:5432/astra"
    )

    # Redis (Phase C PR3 -- generic cache wrapper, core/cache.py; rate
    # limiting is one consumer, not the only one -- see ADR-007)
    redis_url: str = Field(default="redis://127.0.0.1:6379/0")

    # Quotas & rate limiting (PR3) -- enforced locally per-service via the
    # shared JWT-derived user_id, not centralized in the gateway (ADR-007)
    rate_limit_requests_per_minute: int = Field(default=60)
    quota_max_requests_per_month: int = Field(default=2000)
    quota_max_tokens_per_month: int = Field(default=200000)

    # Input microphone device: empty = OS default. Set to a substring of the
    # device name (e.g. "AMD Audio Device") or a numeric sounddevice index.
    # Some Windows mic arrays (e.g. combined webcam+mic modules) silently
    # deliver zero signal even though the stream opens without error, so the
    # OS default is not always usable — use scripts/select_mic_device.py to test and set this.
    mic_device: str = Field(default="")

    log_level: str = Field(default="INFO")

    # LLM generation parameters — controls response length and context window
    llm_num_predict: int = Field(default=300, description="Max tokens per LLM response (0=unlimited)")
    llm_num_ctx: int = Field(default=2048, description="Context window size for LLM")
    llm_temperature: float = Field(default=0.7, description="Sampling temperature for text generation")
    llm_top_p: float = Field(default=0.95, description="Nucleus sampling value")

    # TTS backend: "edge" uses Microsoft Edge TTS (default, no server needed)
    # "piper" strips emotion tags and sends to Piper server
    # "fish_speech" passes emotion tags natively to OpenAudio S1 Mini
    tts_backend: str = Field(default="edge")
    fish_speech_api_url: AnyHttpUrl = Field(default="http://127.0.0.1:8080")
    tts_edge_offline_fallback_enabled: bool = Field(default=True)
    tts_edge_offline_check_url: str = Field(default="https://www.microsoft.com")
    tts_edge_offline_check_timeout_sec: float = Field(default=0.5)
    tts_edge_offline_state_ttl_sec: float = Field(default=3.0)
    tts_edge_timeout_sec: float = Field(default=1.5)

    class Config:
        env_prefix = "AI_ASSISTANT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow vars like AI_ASSISTANT_WHISPER_MODEL_NAME that are read directly
        # via os.getenv (not Settings fields) without tripping extra_forbidden.
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def resolve_host(host: str) -> str:
    """Normalize a bind-all host to a connectable one for client calls.

    Services bind to 0.0.0.0/:: so they're reachable from other containers,
    but a caller on the same machine must dial 127.0.0.1 instead. In Docker
    Compose, host fields are overridden to the service name (e.g. "llm"),
    which passes through unchanged here.
    """
    return "127.0.0.1" if host in ("0.0.0.0", "::") else host
