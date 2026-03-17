"""Merkezi log fonksiyonu - tekrar eden log() tanimlarini birlestir."""
from __future__ import annotations

import datetime
import os


_LOG_FILE = os.environ.get("CLAUDE_MONITOR_LOG", "")


def log(prefix: str, msg: str) -> None:
    """Log mesaji yaz. prefix: 'PRE', 'POST', 'OVERLAY' vb."""
    if not _LOG_FILE:
        return
    try:
        with open(_LOG_FILE, "a") as f:
            ts = datetime.datetime.now().isoformat()
            f.write(f"[{ts}] {prefix} {msg}\n")
    except OSError:
        pass
