#!/usr/bin/env python3
"""
Claude Code Build Monitor -- TUI Overlay  v3.0
  - shared/ modul entegrasyonu (paths, colors, constants, logging)
  - mtime bazli state okuma optimizasyonu
  - JSON hata limiti (graceful shutdown)
  - Platform guvenli SIGWINCH
  - Daraltilmis exception tipleri
"""
from __future__ import annotations

import json
import sys
import os
import time
import signal
import shutil
from pathlib import Path

# ─── Shared imports ──────────────────────────────────────────────────────────

_HOOK_DIR = Path(__file__).parent
_PROJECT_ROOT = _HOOK_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from shared.paths import STATE_FILE, PID_FILE
from shared.logging import log as _log
from shared.colors import (
    RESET, BOLD, DIM, HIDE_CURSOR, SHOW_CURSOR, CLEAR_LINE, MOVE_UP,
    C_PURPLE, C_GREEN, C_RED, C_GRAY, C_WHITE, TOOL_COLORS,
)
from shared.constants import (
    PHASE_INTERVAL_SECS, PROGRESS_DAMPING, OVERLAY_REFRESH_INTERVAL,
    MAX_PROGRESS_PERCENT, MAX_JSON_ERRORS, COMMAND_PREVIEW_LENGTH,
)


def log(msg: str) -> None:
    _log("OVERLAY", msg)

# ─── Spinner & Phases ────────────────────────────────────────────────────────

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

PHASES = {
    "NPM":     ["Resolving deps", "Fetching packages", "Linking modules", "Compiling", "Done"],
    "YARN":    ["Resolving", "Fetching", "Linking", "Building", "Done"],
    "PNPM":    ["Resolving", "Downloading", "Linking", "Building", "Done"],
    "BUN":     ["Resolving", "Linking", "Bundling", "Done"],
    "NX":      ["Workspace graph", "Cache check", "Building", "Done"],
    "TURBO":   ["Reading workspace", "Cache check", "Building", "Done"],
    "LERNA":   ["Bootstrapping", "Building", "Publishing", "Done"],
    "DOCKER":  ["Reading dockerfile", "Pulling base", "Building layers", "Exporting", "Done"],
    "VERCEL":  ["Uploading", "Building", "Routing", "Deploying", "Done"],
    "NETLIFY": ["Uploading", "Building", "Post-processing", "Deploying", "Done"],
    "FLY":     ["Packaging", "Building image", "Deploying", "Health check", "Done"],
    "TF":      ["Refreshing state", "Planning", "Applying", "Done"],
    "PULUMI":  ["Reading stack", "Planning", "Applying", "Done"],
    "K8S":     ["Validating", "Applying", "Rolling out", "Done"],
    "HELM":    ["Fetching chart", "Rendering", "Deploying", "Done"],
    "RUST":    ["Fetching crates", "Compiling deps", "Compiling src", "Linking", "Done"],
    "GO":      ["Downloading", "Compiling", "Linking", "Done"],
    "MAKE":    ["Reading Makefile", "Compiling", "Linking", "Done"],
    "CMAKE":   ["Configuring", "Generating", "Building", "Done"],
    "GRADLE":  ["Resolving deps", "Compiling", "Assembling", "Done"],
    "MVN":     ["Resolving deps", "Compiling", "Packaging", "Done"],
    "PIP":     ["Resolving", "Downloading", "Installing", "Done"],
    "POETRY":  ["Resolving", "Installing", "Done"],
    "UV":      ["Resolving", "Downloading", "Installing", "Done"],
    "TEST":    ["Collecting tests", "Setting up", "Running", "Coverage", "Done"],
    "GIT":     ["Packing objects", "Uploading", "Processing", "Done"],
    "_DEFAULT":["Initializing", "Processing", "Building", "Finalizing", "Done"],
}

# ─── Terminal width ────────────────────────────────────────────────────────────

_terminal_width = 80


def refresh_terminal_width() -> None:
    global _terminal_width
    try:
        _terminal_width = shutil.get_terminal_size().columns
    except (ValueError, OSError):
        _terminal_width = 80


def compute_bar_width() -> int:
    available = _terminal_width - 50
    return max(10, min(available, 40))


def handle_resize(sig, frame):
    refresh_terminal_width()


# Platform guvenli SIGWINCH
if hasattr(signal, "SIGWINCH"):
    signal.signal(signal.SIGWINCH, handle_resize)

# ─── State ────────────────────────────────────────────────────────────────────

_running = True


def handle_term(sig, frame):
    global _running
    _running = False


signal.signal(signal.SIGTERM, handle_term)
signal.signal(signal.SIGINT, handle_term)

# ─── State okuma (mtime cache) ──────────────────────────────────────────────

_last_mtime = 0.0
_cached_commands: list = []


def read_state_if_changed() -> list:
    """Dosya degismediyse cache'den oku, gereksiz I/O yapma."""
    global _last_mtime, _cached_commands
    try:
        current_mtime = STATE_FILE.stat().st_mtime
        if current_mtime == _last_mtime:
            return _cached_commands
        _last_mtime = current_mtime
        raw = STATE_FILE.read_text()
        data = json.loads(raw)
        if isinstance(data, list):
            _cached_commands = data
        return _cached_commands
    except (json.JSONDecodeError, OSError):
        return _cached_commands

# ─── Progress hesaplama ───────────────────────────────────────────────────────

def compute_progress(cmd: dict) -> float:
    elapsed = time.time() - cmd.get("started_at", time.time())
    expected = cmd.get("expected")

    if expected and expected > 0:
        raw = elapsed / expected
        return min(MAX_PROGRESS_PERCENT, raw / (1 + raw * PROGRESS_DAMPING))

    tool = cmd.get("tool", "_DEFAULT")
    phases = PHASES.get(tool, PHASES["_DEFAULT"])
    num_phases = len(phases) - 1
    auto_phase = min(int(elapsed / PHASE_INTERVAL_SECS), num_phases - 1)
    return min(
        (auto_phase / num_phases) + (elapsed % PHASE_INTERVAL_SECS) / (PHASE_INTERVAL_SECS * num_phases * 2),
        0.95,
    )


def get_phase_text(cmd: dict) -> str:
    elapsed = time.time() - cmd.get("started_at", time.time())
    tool = cmd.get("tool", "_DEFAULT")
    phases = PHASES.get(tool, PHASES["_DEFAULT"])
    num_phases = len(phases) - 1
    idx = min(int(elapsed / PHASE_INTERVAL_SECS), num_phases - 1)
    return phases[idx]

# ─── Rendering ────────────────────────────────────────────────────────────────

def render_bar(progress: float) -> str:
    width = compute_bar_width()
    filled = int(progress * width)
    blocks = ["\u2591", "\u2592", "\u2593", "\u2588"]
    partial_f = (progress * width) - filled

    bar = C_PURPLE + "\u2588" * filled
    if filled < width:
        bar += blocks[int(partial_f * len(blocks))]
        bar += DIM + "\u2591" * (width - filled - 1) + RESET
    bar += RESET
    return bar


def fmt_elapsed(started_at: float) -> str:
    s = int(time.time() - started_at)
    m = s // 60
    return f"{m}m {s%60:02d}s" if m else f"{s}s"


def fmt_eta(cmd: dict) -> str:
    expected = cmd.get("expected")
    if not expected:
        return ""
    elapsed = time.time() - cmd.get("started_at", time.time())
    remaining = max(0, expected - elapsed)
    if remaining < 5:
        return ""
    m = int(remaining // 60)
    s = int(remaining % 60)
    eta = f"{m}m {s:02d}s" if m else f"{s}s"
    return f"  ETA {eta}"


def render_cmd_block(cmd: dict, spinner_idx: int) -> list:
    tool       = cmd.get("tool", "BUILD")
    label      = cmd.get("label", "Building...")
    project    = cmd.get("project", "")
    command    = cmd.get("command", "")
    tc         = TOOL_COLORS.get(tool, C_WHITE)

    progress   = compute_progress(cmd)
    phase_text = get_phase_text(cmd)
    spinner    = SPINNER_FRAMES[spinner_idx % len(SPINNER_FRAMES)]
    bar        = render_bar(progress)
    pct        = f"{int(progress * 100):3d}%"
    elapsed    = fmt_elapsed(cmd.get("started_at", time.time()))
    eta        = fmt_eta(cmd)
    cmd_prev   = command[:COMMAND_PREVIEW_LENGTH] + ("..." if len(command) > COMMAND_PREVIEW_LENGTH else "")

    project_str = f"{DIM}{project}  {RESET}" if project else ""
    tag         = f"{tc}{BOLD}[{tool}]{RESET}"

    lines = [
        f"  {spinner}  {tag}  {project_str}{C_WHITE}{BOLD}{label}{RESET}  {DIM}{phase_text}{RESET}",
        f"     {bar}  {C_GRAY}{pct}  {elapsed}{eta}{RESET}",
        f"     {DIM}$ {cmd_prev}{RESET}",
        f"     {DIM}{'-' * min(44, _terminal_width - 6)}{RESET}",
    ]
    return lines


def render_done_block(cmd: dict, success: bool) -> list:
    tool    = cmd.get("tool", "BUILD")
    label   = cmd.get("label", "Build")
    project = cmd.get("project", "")
    tc      = TOOL_COLORS.get(tool, C_WHITE)
    elapsed = fmt_elapsed(cmd.get("started_at", time.time()))

    icon   = f"{C_GREEN}+{RESET}" if success else f"{C_RED}x{RESET}"
    status = "completed" if success else "failed"
    bar    = render_bar(1.0 if success else 0.0)
    pct    = "100%" if success else "  0%"

    project_str = f"{DIM}{project}  {RESET}" if project else ""

    return [
        f"  {icon}  {tc}{BOLD}[{tool}]{RESET}  {project_str}{C_WHITE}{BOLD}{label}{RESET}  {C_GRAY}{status} in {elapsed}{RESET}",
        f"     {bar}  {C_GRAY}{pct}  {elapsed}{RESET}",
        f"     {DIM}{'-' * min(44, _terminal_width - 6)}{RESET}",
    ]

# ─── Main loop ────────────────────────────────────────────────────────────────

def main() -> None:
    global _running

    # State dosyasini bekle
    for _ in range(30):
        if STATE_FILE.exists():
            break
        time.sleep(0.1)
    else:
        sys.exit(0)

    refresh_terminal_width()
    sys.stderr.write(HIDE_CURSOR)
    sys.stderr.flush()

    spinner_idx   = 0
    lines_printed = 0
    json_errors   = 0

    def clear_printed():
        nonlocal lines_printed
        if lines_printed > 0:
            sys.stderr.write(MOVE_UP.format(lines_printed))
            for _ in range(lines_printed):
                sys.stderr.write(CLEAR_LINE + "\n")
            sys.stderr.write(MOVE_UP.format(lines_printed))
            lines_printed = 0

    try:
        while _running:
            commands = read_state_if_changed()

            if not commands:
                json_errors += 1
                if json_errors > MAX_JSON_ERRORS:
                    log("too many empty state reads, exiting")
                    break
                time.sleep(OVERLAY_REFRESH_INTERVAL)
                spinner_idx += 1
                continue

            json_errors = 0  # basarili okuma, sayaci sifirla

            running_cmds = [c for c in commands if c.get("status") == "running"]
            done_cmds    = [c for c in commands if c.get("status") in ("done", "error")]

            if not running_cmds and done_cmds:
                clear_printed()
                for cmd in done_cmds:
                    success = cmd.get("status") == "done"
                    for line in render_done_block(cmd, success):
                        sys.stderr.write(line + "\n")
                sys.stderr.flush()
                break

            output_lines = []
            for cmd in running_cmds:
                output_lines.extend(render_cmd_block(cmd, spinner_idx))

            clear_printed()
            for line in output_lines:
                sys.stderr.write(line + "\n")
            sys.stderr.flush()
            lines_printed = len(output_lines)

            spinner_idx += 1
            time.sleep(OVERLAY_REFRESH_INTERVAL)

    except OSError as e:
        log(f"render error: {e}")
    finally:
        sys.stderr.write(SHOW_CURSOR)
        sys.stderr.flush()
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    main()
