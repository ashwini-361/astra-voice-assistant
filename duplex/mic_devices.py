"""Input device enumeration and resolution.

Some Windows mic arrays open without error but deliver zero real signal
(e.g. combined webcam+mic modules with buggy drivers), so the OS default
input device is not always the right one. This module lets the device be
selected by name/index via config instead of relying on the OS default.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    import sounddevice as sd  # type: ignore
except Exception:  # pylint: disable=broad-except
    sd = None

logger = logging.getLogger(__name__)


def list_input_devices() -> List[Dict[str, Any]]:
    """Return all devices with at least one input channel."""
    if sd is None:
        return []
    devices = []
    for idx, info in enumerate(sd.query_devices()):
        if info.get("max_input_channels", 0) > 0:
            devices.append({"index": idx, "name": info.get("name", ""), "hostapi": info.get("hostapi")})
    return devices


def resolve_device(name_or_index: str) -> Optional[int]:
    """Resolve a config string to a sounddevice device index.

    Accepts a numeric index ("3") or a case-insensitive substring of the
    device name ("AMD Audio Device"). Returns None if unset, unresolvable,
    or sounddevice is unavailable (caller should fall back to OS default).
    """
    name_or_index = (name_or_index or "").strip()
    if not name_or_index or sd is None:
        return None

    if name_or_index.isdigit():
        return int(name_or_index)

    needle = name_or_index.lower()
    for device in list_input_devices():
        if needle in device["name"].lower():
            return device["index"]

    logger.warning("mic_device '%s' did not match any input device; falling back to OS default", name_or_index)
    return None
