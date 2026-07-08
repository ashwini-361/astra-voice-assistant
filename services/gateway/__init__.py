"""Auth-only gateway service. See docs/api/gateway.md.

Not a data-plane proxy -- whisper/llm/tts/intent are called directly by
the frontend. This package owns OAuth login/callback, JWT issuance, and
refresh/logout only.
"""
