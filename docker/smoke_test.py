"""End-to-end smoke test against the live Docker Compose stack.

Run via: docker compose --profile tools run --rm smoke-test (or `make smoke`).

Two stages:
  1. Poll every service's /api/v1/health endpoint (fail fast, name which
     one is down).
  2. Drive intent -> LLM -> TTS as three direct HTTP calls, mirroring exactly
     what the frontend does (see frontend/src/core/api/{intent,llm,tts}.ts) —
     NOT via orchestrator.pipeline.run_pipeline(), which calls TTS's
     /api/v1/voice/playback endpoint. That endpoint decodes and plays audio
     on the *server* via miniaudio/sounddevice for the native single-machine
     CLI/duplex flow; those packages are deliberately excluded from the
     container image (see requirements-container.txt), so it always fails
     headless. /api/v1/voice/speech (used here) just returns audio bytes for
     the caller to play — the actual hosted-web-service path.

Exits 0 on success, 1 on any failure with a clear message about what failed.
"""
import asyncio
import logging
import sys
import time

import httpx

from core.config import get_settings, resolve_host

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smoke_test")

HEALTH_TIMEOUT_SEC = 5.0
HEALTH_RETRIES = 15
HEALTH_RETRY_DELAY_SEC = 2.0
REQUEST_TIMEOUT_SEC = 60.0


def _base_urls() -> dict[str, str]:
    settings = get_settings()
    return {
        "whisper": f"http://{resolve_host(settings.whisper_host)}:{settings.whisper_port}",
        "llm": f"http://{resolve_host(settings.llm_host)}:{settings.llm_port}",
        "tts": f"http://{resolve_host(settings.tts_host)}:{settings.tts_port}",
        "intent": f"http://{resolve_host(settings.intent_host)}:{settings.intent_port}",
    }


async def _check_health(name: str, base_url: str) -> bool:
    url = f"{base_url}/api/v1/health"
    for attempt in range(1, HEALTH_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT_SEC) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    logger.info("[health] %s OK (%s)", name, url)
                    return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.info("[health] %s not ready yet (attempt %d/%d): %s", name, attempt, HEALTH_RETRIES, exc)
        await asyncio.sleep(HEALTH_RETRY_DELAY_SEC)
    logger.error("[health] %s FAILED after %d attempts (%s)", name, HEALTH_RETRIES, url)
    return False


async def _run_health_stage(urls: dict[str, str]) -> bool:
    results = await asyncio.gather(*(_check_health(name, url) for name, url in urls.items()))
    return all(results)


async def _run_pipeline_stage(urls: dict[str, str]) -> bool:
    text = "hello, what can you help me with?"
    timings: dict[str, float] = {}

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SEC) as client:
        start = time.perf_counter()
        intent_resp = await client.post(f"{urls['intent']}/api/v1/voice/intents", json={"text": text})
        timings["intent_ms"] = (time.perf_counter() - start) * 1000
        if intent_resp.status_code != 200:
            logger.error("[intent] FAILED: status=%s body=%s", intent_resp.status_code, intent_resp.text)
            return False
        intent_data = intent_resp.json()
        logger.info("[intent] label=%s provider=%s (%.0fms)", intent_data.get("label"), intent_data.get("provider"), timings["intent_ms"])

        start = time.perf_counter()
        llm_resp = await client.post(f"{urls['llm']}/api/v1/chat/completions", json={"prompt": text, "stream": False})
        timings["llm_ms"] = (time.perf_counter() - start) * 1000
        if llm_resp.status_code != 200:
            logger.error("[llm] FAILED: status=%s body=%s", llm_resp.status_code, llm_resp.text)
            return False
        llm_data = llm_resp.json()
        assistant_text = llm_data.get("response", "")
        logger.info("[llm] model=%s response=%r (%.0fms)", llm_data.get("model"), assistant_text, timings["llm_ms"])
        if not assistant_text.strip():
            logger.error("[llm] FAILED: empty response")
            return False

        start = time.perf_counter()
        tts_resp = await client.post(f"{urls['tts']}/api/v1/voice/speech", json={"text": assistant_text})
        timings["tts_ms"] = (time.perf_counter() - start) * 1000
        if tts_resp.status_code != 200:
            logger.error("[tts] FAILED: status=%s body=%s", tts_resp.status_code, tts_resp.text)
            return False
        logger.info("[tts] audio_bytes=%d (%.0fms)", len(tts_resp.content), timings["tts_ms"])
        if len(tts_resp.content) == 0:
            logger.error("[tts] FAILED: empty audio response")
            return False

    logger.info("[pipeline] timings_ms=%s total_ms=%.0f", timings, sum(timings.values()))
    return True


async def main() -> int:
    urls = _base_urls()

    logger.info("=== Stage 1: service health ===")
    if not await _run_health_stage(urls):
        logger.error("Health stage failed — one or more services are not reachable.")
        return 1

    logger.info("=== Stage 2: end-to-end pipeline (intent -> LLM -> TTS) ===")
    if not await _run_pipeline_stage(urls):
        logger.error("Pipeline stage failed.")
        return 1

    logger.info("=== Smoke test PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
