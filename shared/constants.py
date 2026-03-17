"""Merkezi sabitler - sihirli sayilari birlestir."""
from __future__ import annotations

import os

# Overlay
PHASE_INTERVAL_SECS = int(os.environ.get("CLAUDE_MONITOR_PHASE_INTERVAL", "8"))
PROGRESS_DAMPING = 0.3
OVERLAY_REFRESH_INTERVAL = 0.1
MAX_PROGRESS_PERCENT = 0.97
OVERLAY_CLOSE_DELAY = 0.4

# Komut
COMMAND_MAX_LENGTH = 120
COMMAND_PREVIEW_LENGTH = 55

# Git
GIT_TIMEOUT_SECS = 2

# Overlay hata limiti
MAX_JSON_ERRORS = 10
