"""Atomic dosya kilitleme - state dosyasi race condition onlemi."""
from __future__ import annotations

import fcntl
import json
from pathlib import Path
from contextlib import contextmanager


@contextmanager
def locked_state(state_file: Path):
    """State dosyasini kilitli oku-yaz. Atomic write (tmp + rename)."""
    lock_file = state_file.with_suffix(".lock")
    lock_file.touch(exist_ok=True)
    fd = open(lock_file, "r")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        # Oku
        try:
            data = json.loads(state_file.read_text()) if state_file.exists() else []
        except (json.JSONDecodeError, OSError):
            data = []
        if not isinstance(data, list):
            data = []
        yield data
        # Yaz (atomic: once tmp'ye yaz, sonra rename)
        tmp = state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.rename(state_file)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
