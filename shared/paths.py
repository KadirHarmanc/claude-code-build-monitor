"""Guvenli path yonetimi - /tmp race condition onlemi."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _get_state_dir() -> Path:
    """Kullaniciya ozel, guvenli gecici dizin olustur."""
    # XDG_RUNTIME_DIR varsa kullan (Linux, kullaniciya ozel, guvenli)
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        state_dir = Path(runtime) / "claude_build_monitor"
    else:
        # Fallback: tmpdir altinda UID ile izole et
        uid = os.getuid()
        state_dir = Path(tempfile.gettempdir()) / f"claude_build_monitor_{uid}"

    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    # Sahiplik kontrolu - baska kullanicinin dizinini kullanma
    if state_dir.stat().st_uid != os.getuid():
        raise PermissionError(f"State directory owned by wrong user: {state_dir}")

    return state_dir


STATE_DIR   = _get_state_dir()
STATE_FILE  = STATE_DIR / "current.json"
PID_FILE    = STATE_DIR / "overlay.pid"
HISTORY_DB  = Path.home() / ".claude" / "build_history.db"
SOUNDS_CONFIG = Path.home() / ".claude" / "monitor_sounds.json"
