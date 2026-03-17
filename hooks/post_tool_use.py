#!/usr/bin/env python3
"""
Claude Code Build Monitor -- PostToolUse Hook  v3.0
  - shared/ modul entegrasyonu (paths, logging, db, filelock)
  - OSAScript injection onlemi
  - Guvenli /tmp path
  - Daraltilmis exception tipleri
  - Gelismis komut eslestirme (difflib)
  - Ses cache + monitor_sounds.json entegrasyonu
"""
from __future__ import annotations

import json
import sys
import os
import re
import subprocess
import signal
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

if os.environ.get("CLAUDE_MONITOR_DISABLE", "").strip() == "1":
    sys.exit(0)

# ─── Shared imports ──────────────────────────────────────────────────────────

_HOOK_DIR = Path(__file__).parent
_PROJECT_ROOT = _HOOK_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from shared.paths import STATE_FILE, PID_FILE, SOUNDS_CONFIG
from shared.logging import log as _log
from shared.db import record_build
from shared.filelock import locked_state
from shared.constants import OVERLAY_CLOSE_DELAY


def log(msg: str) -> None:
    _log("POST", msg)

# ─── Exit code parse ──────────────────────────────────────────────────────────

def parse_exit_code(tool_response: dict) -> int:
    if not isinstance(tool_response, dict):
        return 0

    if "exit_code" in tool_response:
        try:
            return int(tool_response["exit_code"])
        except (ValueError, TypeError):
            pass

    content = tool_response.get("content", "")
    if isinstance(content, str):
        m = re.search(r'exit(?:ed)?\s+(?:with\s+)?(?:code\s+)?(\d+)', content, re.I)
        if m:
            return int(m.group(1))
        if re.search(r'\b(error|failed|failure|exception|aborted)\b', content, re.I):
            return 1

    if "error" in tool_response and tool_response["error"]:
        return 1

    return 0

# ─── State: paralel komut tamamlama (kilitli) ───────────────────────────────

def mark_command_done(status: str, command_snippet: str) -> Optional[dict]:
    """Aktif komutlar arasinda eslesen komutu bul, durumunu guncelle."""
    try:
        matched = None
        with locked_state(STATE_FILE) as commands:
            for cmd in commands:
                if cmd.get("status") != "running":
                    continue
                stored_cmd = cmd.get("command", "")
                if command_snippet and stored_cmd.startswith(command_snippet[:40]):
                    matched = cmd
                    cmd["status"] = status
                    break

            # Eslesme yoksa gelismis eslestirme
            if not matched:
                running = [c for c in commands if c.get("status") == "running"]
                if len(running) == 1:
                    matched = running[0]
                    matched["status"] = status
                elif running:
                    best_ratio = 0.0
                    best_cmd = None
                    for c in running:
                        ratio = SequenceMatcher(
                            None, command_snippet[:40], c.get("command", "")[:40]
                        ).ratio()
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_cmd = c
                    if best_cmd and best_ratio > 0.3:
                        matched = best_cmd
                        matched["status"] = status
                    elif running:
                        matched = running[0]
                        matched["status"] = status
                        log(f"fuzzy match failed, closing oldest: {matched.get('id')}")

        return matched
    except OSError as e:
        log(f"mark_command_done error: {e}")
        return None

# ─── Overlay durdurma ────────────────────────────────────────────────────────

def stop_overlay_if_idle() -> None:
    """Calisan komut kalmadiysa overlay'i kapat."""
    try:
        with locked_state(STATE_FILE) as commands:
            still_running = [c for c in commands if c.get("status") == "running"]
            if still_running:
                log(f"{len(still_running)} commands still running, keeping overlay")
                return
    except OSError:
        pass

    time.sleep(OVERLAY_CLOSE_DELAY)

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            log(f"overlay stopped (pid={pid})")
        except (ValueError, ProcessLookupError, OSError):
            pass
        finally:
            PID_FILE.unlink(missing_ok=True)

# ─── Ses ─────────────────────────────────────────────────────────────────────

_sound_cache: dict = {}


def _load_sound_config() -> dict:
    """monitor_sounds.json dosyasindan ses konfigurasyonunu oku."""
    if SOUNDS_CONFIG.exists():
        try:
            return json.loads(SOUNDS_CONFIG.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def find_sound(success: bool) -> Optional[str]:
    cache_key = "success" if success else "failure"
    if cache_key in _sound_cache:
        return _sound_cache[cache_key]

    # 1. Environment variable override
    custom = os.environ.get("CLAUDE_MONITOR_SOUND", "").strip()
    if custom.lower() == "none":
        _sound_cache[cache_key] = None
        return None
    if custom and Path(custom).exists():
        _sound_cache[cache_key] = custom
        return custom

    # 2. monitor_sounds.json konfigurasyonu
    config = _load_sound_config()
    if not config.get("enabled", True):
        _sound_cache[cache_key] = None
        return None

    active_key = "active_success" if success else "active_failure"
    active_name = config.get(active_key, "")
    if active_name:
        for s in config.get("custom_sounds", []):
            if s.get("name") == active_name and Path(s.get("path", "")).exists():
                _sound_cache[cache_key] = s["path"]
                return s["path"]

    # 3. Sistem varsayilanlari
    result = None
    if sys.platform == "darwin":
        base = Path("/System/Library/Sounds")
        names = (
            ["Tink.aiff", "Pop.aiff", "Glass.aiff"] if success
            else ["Basso.aiff", "Funk.aiff", "Tink.aiff"]
        )
        for n in names:
            f = base / n
            if f.exists():
                result = str(f)
                break
    elif sys.platform.startswith("linux"):
        base = Path("/usr/share/sounds/freedesktop/stereo")
        names = (
            ["complete.oga", "message-new-instant.oga", "dialog-information.oga"] if success
            else ["dialog-error.oga", "dialog-warning.oga", "complete.oga"]
        )
        for n in names:
            f = base / n
            if f.exists():
                result = str(f)
                break

    _sound_cache[cache_key] = result
    return result


def play_sound(success: bool) -> None:
    sound = find_sound(success)
    if not sound:
        return
    try:
        if sys.platform == "darwin":
            subprocess.Popen(
                ["afplay", sound],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        elif sys.platform.startswith("linux"):
            for player in ["paplay", "aplay", "mpg123"]:
                try:
                    subprocess.Popen(
                        [player, sound],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    break
                except FileNotFoundError:
                    continue
    except OSError:
        pass

# ─── Native OS bildirimi ──────────────────────────────────────────────────────

def _escape_applescript(s: str) -> str:
    """AppleScript string literal icin ozel karakterleri escape et."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def terminal_is_focused() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=1,
        )
        name = r.stdout.strip().lower()
        return any(t in name for t in ["terminal", "iterm", "warp", "alacritty", "kitty", "hyper"])
    except (subprocess.SubprocessError, OSError):
        return False


def send_native_notification(cmd: dict, success: bool, duration: float) -> None:
    label   = cmd.get("label", "Build")
    project = cmd.get("project", "")
    icon    = "+" if success else "x"
    status  = "completed" if success else "failed"
    dur_str = f"{int(duration)}s" if duration < 60 else f"{int(duration//60)}m {int(duration%60):02d}s"
    title   = f"Claude Code -- {project}" if project else "Claude Code"
    body    = f"{icon} {label} {status} in {dur_str}"

    if sys.platform == "darwin":
        if terminal_is_focused():
            return
        try:
            safe_body  = _escape_applescript(body)
            safe_title = _escape_applescript(title)
            script = f'display notification "{safe_body}" with title "{safe_title}"'
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    elif sys.platform.startswith("linux"):
        icon_name = "dialog-information" if success else "dialog-error"
        try:
            subprocess.Popen(
                ["notify-send", "--icon", icon_name, "--expire-time", "4000", title, body],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pass
        except OSError:
            pass

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    if not STATE_FILE.exists():
        sys.exit(0)

    command   = data.get("tool_input", {}).get("command", "")
    response  = data.get("tool_response", {})
    exit_code = parse_exit_code(response)
    success   = (exit_code == 0)
    status    = "done" if success else "error"

    log(f"exit_code={exit_code} success={success} cmd={command[:60]!r}")

    matched = mark_command_done(status, command)

    if matched:
        duration = time.time() - matched.get("started_at", time.time())
        record_build(matched, duration, success)
        send_native_notification(matched, success, duration)

    stop_overlay_if_idle()
    play_sound(success)

    sys.exit(0)


if __name__ == "__main__":
    main()
