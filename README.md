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
- `GET /settings`
- `POST /settings`
- `POST /settings/reset`
- `GET /streaming-config`

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
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
curl http://127.0.0.1:8003/health
curl http://127.0.0.1:8004/health
.\start_stack.ps1
```

## Quick start (Docker Compose, one command)
This is Phase W-1 of `docs/ASTRA_WEB_SERVICE_PLAN.md` — a reproducible dev
environment as a prerequisite for eventual hosted deployment. It runs
whisper/llm/tts/intent + Qdrant in containers; the frontend still runs
natively (`npm run dev`).

```powershell
# One-time: install `make` if you don't have it (choco install make, or
# scoop install make). Without make, run the docker compose commands
# shown in each Makefile target directly instead.
copy .env.example .env
ollama serve   # Ollama stays native — see "Architecture" below
make up        # or: make up-gpu   (GPU passthrough for whisper)
docker compose ps   # wait for all 5 services to show "healthy"
make seed
make smoke
```
`make smoke` calls `/classify`, `/generate`, and `/synthesize` directly —
the same endpoints the frontend uses (not `orchestrator/pipeline.py`'s
`/speak`, which decodes+plays audio server-side via miniaudio/sounddevice,
deliberately excluded from the container image — a local-machine CLI
feature, not applicable to a hosted service). Expected output: all 4
service health checks pass, a real intent label, a real Astra-persona LLM
response, real synthesized audio bytes, per-stage timings, exit code 0.

`make lint` runs ruff + black --check + pytest (installs `ruff`/`black`
into `venv` on first run via `requirements-dev.txt`).

Other targets: `make down`, `make logs`, `make clean` (also removes the
Qdrant volume and whisper's HF model cache volume).

### Architecture (current, W-1 scope — no gateway yet)
```
Frontend (native, npm run dev)
    |-- POST /transcribe        --> Whisper  (STT, container)
    |-- POST /generate,/agent/loop --> LLM   (container) --> Ollama (native host, NOT containerized)
    |-- POST /synthesize        --> TTS      (container) --> edge-tts (outbound HTTPS)
    |-- POST /classify          --> Intent   (container, CPU-only onnxruntime)
                                       |
                                       v
                                   Qdrant (container; memory/vector_store.py)
```

### Deliberately deferred from this compose stack
- **Postgres/Redis**: not included. Nothing in the codebase references any
  ORM/session/user concept yet — that arrives in Phase W3 (auth) of the web
  service plan, where a real schema will exist to seed. Empty containers
  today would be pure maintenance risk with no consumer.
- **Ollama**: stays native/external, reached via
  `http://host.docker.internal:11434`, rather than containerized — avoids
  re-doing cloud sign-in / model pulls inside a container and duplicated
  model caches. Revisit when deploying to a dedicated GPU server with no
  pre-existing native Ollama setup to preserve.
- **User seeding**: `make seed` seeds sample Qdrant memories, not a
  database/user record — there's no user table yet (Phase W3).

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
