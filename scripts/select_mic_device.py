"""Test every input-capable audio device and select the one to use.

Some devices (notably combined webcam+mic arrays) open without error but
deliver zero real signal — the only way to tell is to actually record from
each one and look at the RMS level. This script does that, then writes the
chosen device name to .env as AI_ASSISTANT_MIC_DEVICE so the rest of the
app picks it up (see duplex/mic_devices.py) without any code change.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("sounddevice not installed in this environment.")
    sys.exit(1)

from duplex.mic_devices import list_input_devices

RECORD_SECONDS = 2.5
SILENT_RMS_THRESHOLD = 5.0  # below this, treat as "no real signal"


def record_rms(device_index: int) -> tuple[float, float, str]:
    """Record briefly from a device. Returns (avg_rms, max_rms, error)."""
    frames: list[np.ndarray] = []
    error = ""

    def callback(indata, _frames, _time_info, _status):
        frames.append(indata.copy())

    try:
        with sd.InputStream(
            device=device_index,
            samplerate=16000,
            channels=1,
            dtype="int16",
            callback=callback,
        ):
            time.sleep(RECORD_SECONDS)
    except Exception as exc:  # pylint: disable=broad-except
        return 0.0, 0.0, str(exc)

    if not frames:
        return 0.0, 0.0, "no frames delivered"

    data = np.concatenate(frames).astype(np.float32)
    rms = float(np.sqrt(np.mean(data ** 2)))
    peak = float(np.max(np.abs(data)))
    return rms, peak, error


def write_env(device_name: str) -> None:
    env_path = Path(__file__).parent / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    key = "AI_ASSISTANT_MIC_DEVICE"
    new_line = f"{key}={device_name}"
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = new_line
            found = True
            break
    if not found:
        lines.append(new_line)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {new_line} to {env_path}")


def main() -> None:
    devices = list_input_devices()
    if not devices:
        print("No input devices found (or sounddevice unavailable).")
        return

    print("=" * 70)
    print("MIC DEVICE TEST")
    print("=" * 70)
    print(f"Found {len(devices)} input-capable device(s). Testing each for")
    print(f"{RECORD_SECONDS}s — SPEAK OR MAKE NOISE during every test.\n")

    results = []
    for d in devices:
        input(f"Press Enter, then talk to test [{d['index']}] {d['name']} ...")
        rms, peak, error = record_rms(d["index"])
        status = "ERROR" if error else ("SILENT" if rms < SILENT_RMS_THRESHOLD else "OK")
        results.append({**d, "rms": rms, "peak": peak, "error": error, "status": status})
        if error:
            print(f"   -> {status}: {error}\n")
        else:
            print(f"   -> {status}  (avg_rms={rms:.1f}, peak={peak:.0f})\n")

    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    for r in results:
        marker = "+" if r["status"] == "OK" else "-"
        print(f" {marker} [{r['index']}] {r['name']:45s} {r['status']:7s} rms={r['rms']:.1f}")

    working = [r for r in results if r["status"] == "OK"]
    if not working:
        print("\nNo device captured real signal. Check OS mic mute/volume/privacy settings.")
        return

    print("\nWorking device(s) found:")
    for r in working:
        print(f"  [{r['index']}] {r['name']}")

    choice = input("\nEnter the index to save as your mic device (blank = skip saving): ").strip()
    if not choice:
        return
    chosen = next((r for r in results if str(r["index"]) == choice), None)
    if chosen is None:
        print("Invalid index, nothing saved.")
        return
    write_env(chosen["name"])
    print("Restart any running services (start_stack.ps1) for the change to take effect.")


if __name__ == "__main__":
    main()
