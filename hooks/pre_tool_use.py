#!/usr/bin/env python3
"""
Claude Code Build Monitor -- PreToolUse Hook  v3.0
  - shared/ modul entegrasyonu (paths, logging, db, patterns, filelock)
  - Guvenli /tmp path (UID bazli izolasyon)
  - Komut sanitizasyonu (hassas veri redaksiyonu)
  - Proje context cache
  - Daraltilmis exception tipleri
  - Type hint'ler
"""
from __future__ import annotations

import json
import sys
import os
import subprocess
import re
import time
import uuid
import hashlib
from pathlib import Path
from typing import Optional, Dict

# ─── Disable flag ─────────────────────────────────────────────────────────────

if os.environ.get("CLAUDE_MONITOR_DISABLE", "").strip() == "1":
    sys.exit(0)

# ─── Shared imports ──────────────────────────────────────────────────────────

_HOOK_DIR = Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

from shared.paths import STATE_FILE, PID_FILE
from shared.logging import log as _log
from shared.db import init_db, get_expected_duration
from shared.patterns import detect_build_command
from shared.filelock import locked_state
from shared.constants import COMMAND_MAX_LENGTH, GIT_TIMEOUT_SECS


def log(msg: str) -> None:
    _log("PRE", msg)

# ─── Komut sanitizasyonu ─────────────────────────────────────────────────────

def sanitize_command(cmd: str, max_len: int = COMMAND_MAX_LENGTH) -> str:
    """Hassas verileri gizle, sonra kisalt."""
    sanitized = re.sub(
        r'(--?(?:token|key|password|secret|auth)[= ]\s*)(\S+)',
        r'\1[REDACTED]',
        cmd,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(r'://[^@\s]+@', '://[REDACTED]@', sanitized)
    if len(sanitized) > max_len:
        return sanitized[:max_len - 3] + "..."
    return sanitized

# ─── Proje baglami (cache'li) ────────────────────────────────────────────────

_project_cache: Dict[str, dict] = {}


def get_project_context() -> dict:
    cwd = Path.cwd()
    cwd_str = str(cwd)

    if cwd_str in _project_cache:
        return _project_cache[cwd_str]

    name = cwd.name
    version: Optional[str] = None
    git_root = cwd_str

    # package.json
    pkg = cwd / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
            name = data.get("name", name)
            version = data.get("version")
        except (json.JSONDecodeError, OSError):
            pass

    # git bilgisi
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=cwd, timeout=GIT_TIMEOUT_SECS,
        )
        if r.returncode == 0:
            git_root = r.stdout.strip()
            r2 = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, cwd=cwd, timeout=GIT_TIMEOUT_SECS,
            )
            if r2.returncode == 0:
                m = re.search(r'[/:]([^/:]+?)(?:\.git)?$', r2.stdout.strip())
                if m:
                    name = m.group(1)
    except (subprocess.SubprocessError, OSError):
        pass

    project_id = hashlib.md5(git_root.encode()).hexdigest()[:8]
    result = {"name": name, "version": version, "id": project_id}
    _project_cache[cwd_str] = result
    return result

# ─── Overlay baslatma ─────────────────────────────────────────────────────────

def launch_overlay() -> None:
    overlay_script = _HOOK_DIR / "overlay.py"
    if not overlay_script.exists():
        log("overlay.py not found, skipping")
        return

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            log(f"overlay already running (pid={pid})")
            return
        except (ValueError, ProcessLookupError, OSError):
            PID_FILE.unlink(missing_ok=True)

    try:
        proc = subprocess.Popen(
            [sys.executable, str(overlay_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        PID_FILE.write_text(str(proc.pid))
        log(f"overlay launched (pid={proc.pid})")
    except OSError as e:
        log(f"overlay launch failed: {e}")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    # Bilinen build araci mi, yoksa genel komut mu?
    result = detect_build_command(command)
    if result:
        label, tool = result
        mode = "full"
    else:
        # Genel komut: kisa gosterim
        cmd_name = command.strip().split()[0].split("/")[-1] if command.strip() else "cmd"
        label = cmd_name
        tool = "CMD"
        mode = "mini"

    log(f"detected [{tool}] {label!r} mode={mode}  cmd={command[:60]!r}")

    ctx = get_project_context()
    expected = get_expected_duration(tool, ctx["id"]) if mode == "full" else None
    log(f"project={ctx['name']!r} id={ctx['id']} expected={expected}s")

    init_db()

    safe_command = sanitize_command(command)
    with locked_state(STATE_FILE) as commands:
        commands[:] = [c for c in commands if c.get("status") == "running"]
        commands.append({
            "id":           str(uuid.uuid4())[:8],
            "label":        label,
            "tool":         tool,
            "mode":         mode,
            "command":      safe_command,
            "project":      ctx["name"],
            "project_id":   ctx["id"],
            "status":       "running",
            "started_at":   time.time(),
            "expected":     expected,
        })

    launch_overlay()
    sys.exit(0)


if __name__ == "__main__":
    main()
