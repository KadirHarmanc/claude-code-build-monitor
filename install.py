#!/usr/bin/env python3
"""
Claude Code Build Monitor -- Installer v3
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HOOKS_DIR   = Path.home() / ".claude" / "hooks"
SETTINGS    = Path.home() / ".claude" / "settings.json"
SCRIPT_DIR  = Path(__file__).parent / "hooks"
SHARED_DIR  = Path(__file__).parent / "shared"
CLI_SRC     = Path(__file__).parent / "claude-monitor"
CLI_DST     = Path.home() / ".local" / "bin" / "claude-monitor"
TARGET_SHARED = HOOKS_DIR.parent / "monitor_shared"


def print_banner():
    print("""
+==========================================+
|  Claude Code Build Monitor -- Installer  |
+==========================================+
""")


def check_python():
    if sys.version_info < (3, 8):
        print("x  Python 3.8+ required")
        sys.exit(1)
    print(f"+  Python {sys.version_info.major}.{sys.version_info.minor}")


def copy_hooks():
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["pre_tool_use.py", "post_tool_use.py", "overlay.py"]:
        src = SCRIPT_DIR / name
        dst = HOOKS_DIR / name
        if not src.exists():
            print(f"x  Not found: {src}")
            sys.exit(1)
        shutil.copy2(src, dst)
        dst.chmod(0o755)
        print(f"+  {name} -> {dst}")


def copy_shared():
    """shared/ modulunu ~/.claude/monitor_shared/ olarak kopyala."""
    if not SHARED_DIR.exists():
        print(f"x  shared/ dizini bulunamadi: {SHARED_DIR}")
        sys.exit(1)
    if TARGET_SHARED.exists():
        shutil.rmtree(TARGET_SHARED)
    shutil.copytree(SHARED_DIR, TARGET_SHARED)
    print(f"+  shared/ -> {TARGET_SHARED}")


def install_cli():
    if not CLI_SRC.exists():
        print(".  CLI binary not found, skipping")
        return
    try:
        CLI_DST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CLI_SRC, CLI_DST)
        CLI_DST.chmod(0o755)
        print(f"+  CLI installed: {CLI_DST}")
        import os
        path_dirs = os.environ.get("PATH", "").split(":")
        if str(CLI_DST.parent) not in path_dirs:
            print(f'.  Add to PATH: export PATH="$HOME/.local/bin:$PATH"')
    except OSError as e:
        print(f".  CLI install skipped: {e}")


def update_settings():
    if SETTINGS.exists():
        try:
            with open(SETTINGS) as f:
                config = json.load(f)
        except json.JSONDecodeError:
            config = {}
    else:
        config = {}

    hooks = config.setdefault("hooks", [])
    pre_cmd  = f"python3 {HOOKS_DIR}/pre_tool_use.py"
    post_cmd = f"python3 {HOOKS_DIR}/post_tool_use.py"

    existing = [inner.get("command", "") for h in hooks for inner in h.get("hooks", [])]
    added = []
    if pre_cmd not in existing:
        hooks.insert(0, {"event": "PreToolUse", "matcher": "Bash",
                          "hooks": [{"type": "command", "command": pre_cmd}]})
        added.append("PreToolUse")
    if post_cmd not in existing:
        hooks.append({"event": "PostToolUse", "matcher": "Bash",
                       "hooks": [{"type": "command", "command": post_cmd}]})
        added.append("PostToolUse")

    with open(SETTINGS, "w") as f:
        json.dump(config, f, indent=2)

    if added:
        print(f"+  Hooks registered: {', '.join(added)}")
    else:
        print("+  Hooks already registered")


def print_done():
    sound_note = ""
    if sys.platform == "darwin":
        sound_note = "\n  Sound: Tink.aiff (system) -- set via 'claude-monitor sound' to change"
    else:
        sound_note = "\n  Sound: complete.oga (system) -- set via 'claude-monitor sound' to change"

    print(f"""
Installation complete!
{sound_note}
  Hooks  : {HOOKS_DIR}
  Shared : {TARGET_SHARED}
  CLI    : {CLI_DST}

Restart Claude Code to activate.
Use 'claude-monitor --help' for management commands.
Use 'claude-monitor sound list' to manage notification sounds.
""")


if __name__ == "__main__":
    print_banner()
    check_python()
    copy_hooks()
    copy_shared()
    install_cli()
    update_settings()
    print_done()
