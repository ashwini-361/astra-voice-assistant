# Shared image for whisper/llm/tts/intent services (Phase W-1).
# The specific service is selected at the docker-compose.yml `command:`
# level, not baked into the image, since all four share the same
# requirements, core/, memory/, orchestrator/ code.
#
# One shared image trades a larger build (torch/ctranslate2 included even
# for services that don't need them) for a much simpler Dockerfile/build
# pipeline. If build time or image size becomes a real problem, split
# whisper into its own Dockerfile.whisper — not needed for W-1.
FROM python:3.11-slim

# curl: used by every service's compose healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-container.txt .
# ctranslate2's bundled libctranslate2-*.so ships with an executable-stack
# ELF flag (PT_GNU_STACK, PF_X set) that this container kernel (observed on
# Docker Desktop/WSL2) refuses to mmap, failing with "cannot enable
# executable stack ... Invalid argument" at import time. Debian bookworm
# doesn't package the usual `execstack` CLI fix, so clear the flag directly
# via a small stdlib-only ELF patch (verified empirically against this
# exact file/kernel before being added here) — no extra dependency needed.
RUN pip install --no-cache-dir -r requirements-container.txt \
    && python3 - <<'PYEOF'
import glob
import struct

PT_GNU_STACK = 0x6474e551
PF_X = 0x1

for path in glob.glob(
    "/usr/local/lib/python3.11/site-packages/**/libctranslate2*.so*",
    recursive=True,
):
    with open(path, "rb") as f:
        data = bytearray(f.read())
    if data[:4] != b"\x7fELF" or data[4] != 2:
        continue
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        if struct.unpack_from("<I", data, off)[0] == PT_GNU_STACK:
            flags_off = off + 4
            flags = struct.unpack_from("<I", data, flags_off)[0]
            struct.pack_into("<I", data, flags_off, flags & ~PF_X)
            print(f"cleared executable-stack flag on {path}: {flags:#x} -> {flags & ~PF_X:#x}")
    with open(path, "wb") as f:
        f.write(data)
PYEOF

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# No default CMD: docker-compose.yml sets `command:` per service, e.g.
#   uvicorn services.whisper_service:app --host 0.0.0.0 --port 8001
