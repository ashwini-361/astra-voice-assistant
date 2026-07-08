# Voice2

YC-style summary: we are building the fastest local voice assistant for Windows laptops.

## Problem
Current local assistants feel slow, robotic, and fragile under interruption.

## Solution
Voice2 is a local-first, low-latency voice stack with:
- Whisper ASR
- Ollama LLM streaming
- Edge/Piper/Fish-Speech TTS
- Intent routing + memory
- interruption-safe duplex orchestration

## Why now
Consumer laptops now have enough GPU/CPU throughput for practical on-device assistants without cloud dependency.

## What improved recently
- True decoupled LLM->TTS streaming (producer/consumer)
- Adaptive chunking: fast first speech, smoother follow-up speech
- Runtime TTS settings API (`/settings`, `/streaming-config`)
- Slightly faster Edge default speech (`edge_base_rate_pct=8`)
- Earlier no-tag flushes for lower first-audio latency
- Better interruption handling and stale-generation guards

## Core architecture
- `services/whisper_service.py` - ASR
- `services/llm_service.py` - provider gateway
- `services/tts_service.py` - synthesis + playback control
- `orchestrator/pipeline.py` - turn pipeline + timing
- `streaming/llm_streamer.py` - token stream
- `streaming/tts_streamer.py` - adaptive speech chunk stream
- `duplex/` - interrupt and stream management

## TTS runtime control API
- `GET /api/v1/voice/settings`
- `POST /api/v1/voice/settings`
- `POST /api/v1/voice/settings/reset`
- `GET /api/v1/voice/streaming-config`

Important tunables:
- `edge_base_rate_pct`
- `edge_offline_fallback_enabled`
- `edge_offline_check_url`
- `edge_offline_check_timeout_sec`
- `edge_offline_state_ttl_sec`
- `edge_timeout_sec`
- `chunk_initial_words`
- `chunk_steady_words`
- `chunk_max_chars`
- `piper_api_url`
- `piper_voice` (defaults to `en_US-lessac-medium`, a female Piper voice)
- `piper_speaker_id`
- `fish_speech_api_url`

Offline routing behavior:
- If backend is `edge` and network probe says offline, TTS routes directly to Piper.
- If backend is `edge` but Edge synthesis errors/times out, TTS falls back to Piper.

Model cache behavior:
- `setup.ps1` and `start_stack.ps1` export `HF_HOME=.hf_cache` and `HUGGINGFACE_HUB_CACHE=.hf_cache/hub`.
- This keeps downloaded CPU models cached locally so they are reused instead of downloaded repeatedly.

## Quick start (native, Windows)
```powershell
.\setup.ps1
.\start_stack.ps1 -ServicesOnly
curl http://127.0.0.1:8001/api/v1/health
curl http://127.0.0.1:8002/api/v1/health
curl http://127.0.0.1:8003/api/v1/health
curl http://127.0.0.1:8004/api/v1/health
.\start_stack.ps1
```

## Quick start (Docker Compose, one command)
This is Phase W-1 of `docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md` — a reproducible dev
environment as a prerequisite for eventual hosted deployment. It runs
whisper/llm/tts/intent + Qdrant in containers; the frontend still runs
natively (`npm run dev`).

```powershell
# One-time: install `make` if you don't have it (choco install make, or
# scoop install make). Without make, run the docker compose commands
# shown in each Makefile target directly instead.
ollama serve                # Ollama stays native — see "Architecture" below
ollama pull qwen2.5:3b      # small local model .env.example is validated against
make up                     # or: make up-gpu   (GPU passthrough for whisper)
                            # creates .env from .env.example on first run,
                            # runs Postgres migrations (make migrate), then
                            # waits for all 7 services to be healthy
make seed
make smoke
```
`make up` copies `.env.example` to `.env` automatically if `.env` doesn't
exist yet (see the `env` Makefile target), and applies Postgres migrations
automatically (see the `migrate` Makefile target) — no manual steps needed.
`make smoke` calls `/api/v1/voice/intents`, `/api/v1/chat/completions`, and
`/api/v1/voice/speech` directly — the same endpoints the frontend uses (not
`orchestrator/pipeline.py`'s `/api/v1/voice/playback`, which decodes+plays
audio server-side via miniaudio/sounddevice, deliberately excluded from the
container image — a local-machine CLI feature, not applicable to a hosted
service). Expected output: all 5 core-service health checks pass (plus
Postgres/gateway), a real intent label, a real Astra-persona LLM response,
real synthesized audio bytes, per-stage timings, exit code 0.

`make lint` runs ruff + black --check + pytest (installs `ruff`/`black`
into `venv` on first run via `requirements-dev.txt`).

Other targets: `make down`, `make logs`, `make clean` (also removes the
Qdrant volume and whisper's HF model cache volume).

### Architecture (Phase C — multi-user foundation in progress, see docs/adr/ADR-007-multiuser-pivot.md)
```
Frontend (native, npm run dev)
    |-- POST /api/v1/voice/transcriptions        --> Whisper  (STT, container)
    |-- POST /api/v1/chat/completions,/api/v1/agent/loop --> LLM (container) --> Ollama (native host, NOT containerized)
    |-- POST /api/v1/voice/speech                --> TTS      (container) --> edge-tts (outbound HTTPS)
    |-- POST /api/v1/voice/intents                --> Intent   (container, CPU-only onnxruntime)
    |-- (login/refresh only) --> Gateway (container; auth-only, NOT a data-plane proxy)
                                       |
                                       v
                                   Qdrant (container; memory/vector_store.py)
                                   Postgres (container; db/ -- users/conversations/usage_counters,
                                             see db/migrations/)
                                   Redis (container; core/cache.py -- generic wrapper, rate
                                          limiting is one consumer via core/rate_limit.py)
```

### Deliberately deferred from this compose stack
- **Ollama**: stays native/external, reached via
  `http://host.docker.internal:11434`, rather than containerized — avoids
  re-doing cloud sign-in / model pulls inside a container and duplicated
  model caches. Revisit when deploying to a dedicated GPU server with no
  pre-existing native Ollama setup to preserve.
- **User seeding**: `make seed` seeds sample memories (Postgres
  `conversations` + Qdrant) under the reserved local/service user
  (`core.auth.LOCAL_USER_ID`); that row itself is guaranteed to already
  exist by `make migrate`'s data migration, not by `make seed` — see
  `docs/api/auth.md`.

### Version requirements (containerized path)
| Component | Version used/tested |
|---|---|
| Docker Engine | 24.x+ (Docker Desktop with WSL2 backend on Windows) |
| Docker Compose | v2 (bundled with modern Docker Desktop) |
| NVIDIA Container Toolkit | required only for `make up-gpu`; confirm `docker info` shows `Runtimes: nvidia runc` |
| Host GPU driver | CUDA 12.1+ compatible driver (validate against the container's torch/CUDA build — see Known risks below) |

### Resource requirements
- **Minimum**: 16 GB RAM, CPU-only intent + whisper works but whisper STT
  will be noticeably slower without a GPU.
- **Recommended for GPU passthrough**: NVIDIA GPU with 6 GB+ VRAM (tested on
  an RTX 4050 laptop GPU), `make up-gpu`.
- Whisper's first run downloads the `small` model from HuggingFace into a
  named Docker volume (`whisper-hf-cache`) — subsequent starts are fast;
  first start can take a couple of minutes.

### Known risks / things to validate on a new machine
- GPU reservation syntax in `docker-compose.gpu.yml` varies by Docker
  Compose version — if `make up-gpu` fails, check whether your Compose
  version needs `runtime: nvidia` + `NVIDIA_VISIBLE_DEVICES` instead of
  `deploy.resources.reservations.devices`.
- `host.docker.internal` works out of the box on Docker Desktop
  (Windows/Mac); on Linux Docker Engine it needs the `extra_hosts:
  host.docker.internal:host-gateway` entry already present in
  `docker-compose.yml` — confirm this resolves on your setup.
- Plain `onnxruntime` (CPU, used in containers) vs. the native
  `onnxruntime-directml` build may have subtle behavioral differences
  beyond execution provider selection — the intent service's health
  endpoint reports `fallback_mode: true` when running CPU-only; confirm
  this is expected before relying on it.

## Duplex troubleshooting (Windows mic)
If duplex fails with `PortAudioError ... MME error 1`:
1. Verify Windows microphone privacy permission.
2. Close apps that lock microphone input.
3. Re-select default input device in Windows sound settings.
4. Re-run `start_stack.ps1`.

## Validation
Run tests:
```powershell
.\venv\python.exe -m pytest tests -q
```

For focused streaming validation:
```powershell
.\venv\python.exe -m pytest -q tests/test_streaming.py
```
