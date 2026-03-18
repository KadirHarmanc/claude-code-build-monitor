"""ANSI renk kodlari ve TTY destegi kontrolu."""
from __future__ import annotations

import os
import sys


def supports_color() -> bool:
    """Terminal ANSI renk destekliyor mu?"""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stderr, "isatty") or not sys.stderr.isatty():
        return False
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False
    return True


_COLOR = supports_color()


def _c(code: str) -> str:
    return code if _COLOR else ""


# Temel stiller
RESET       = _c("\033[0m")
BOLD        = _c("\033[1m")
DIM         = _c("\033[2m")
HIDE_CURSOR = _c("\033[?25l")
SHOW_CURSOR = _c("\033[?25h")
CLEAR_LINE  = "\033[2K\r"  # Her zaman lazim (cursor kontrolu)
MOVE_UP     = "\033[{}A"

# Renkler
C_PURPLE = _c("\033[38;5;141m")
C_GREEN  = _c("\033[38;5;114m")
C_YELLOW = _c("\033[38;5;221m")
C_BLUE   = _c("\033[38;5;111m")
C_CYAN   = _c("\033[38;5;87m")
C_RED    = _c("\033[38;5;210m")
C_GRAY   = _c("\033[38;5;242m")
C_WHITE  = _c("\033[38;5;255m")
C_ORANGE = _c("\033[38;5;214m")
C_TEAL   = _c("\033[38;5;80m")
C_LIME   = _c("\033[38;5;149m")

# CLI icin kisa alias'lar
GREEN  = C_GREEN
RED    = C_RED
YELLOW = C_YELLOW
BLUE   = C_BLUE
GRAY   = C_GRAY
PURPLE = C_PURPLE
CYAN   = C_CYAN

# Tool renkleri
TOOL_COLORS = {
    "NPM":     C_RED,
    "YARN":    C_BLUE,
    "PNPM":    C_YELLOW,
    "BUN":     C_ORANGE,
    "NX":      C_RED,
    "TURBO":   C_CYAN,
    "LERNA":   C_PURPLE,
    "DOCKER":  C_CYAN,
    "VERCEL":  C_WHITE,
    "NETLIFY": C_GREEN,
    "FLY":     C_PURPLE,
    "CF":      C_YELLOW,
    "AWS":     C_ORANGE,
    "GCP":     C_BLUE,
    "HEROKU":  _c("\033[38;5;99m"),
    "RAILWAY": _c("\033[38;5;213m"),
    "RENDER":  C_GREEN,
    "TF":      C_PURPLE,
    "PULUMI":  _c("\033[38;5;205m"),
    "ANSIBLE": C_RED,
    "K8S":     C_BLUE,
    "HELM":    C_CYAN,
    "RUST":    C_YELLOW,
    "GO":      C_CYAN,
    "MAKE":    C_GRAY,
    "CMAKE":   C_GRAY,
    "GRADLE":  C_LIME,
    "MVN":     C_RED,
    "PIP":     C_BLUE,
    "POETRY":  C_CYAN,
    "UV":      C_TEAL,
    "SWIFT":   C_ORANGE,
    "XCODE":   C_BLUE,
    "TEST":    C_GREEN,
    "GIT":     C_PURPLE,
    "CMD":     C_GRAY,
    "WEBPACK": C_BLUE,
    "ESBUILD": C_YELLOW,
    "ROLLUP":  C_RED,
    "VITE":    C_PURPLE,
    "PARCEL":  C_ORANGE,
    "TSUP":    C_CYAN,
    "UNBUILD": C_TEAL,
    "DENO":    C_GREEN,
    "PODMAN":  C_PURPLE,
    "BUILDAH": C_RED,
    "RUBY":    C_RED,
    "PHP":     C_PURPLE,
    "DOTNET":  C_BLUE,
    "BAZEL":   C_GREEN,
    "BUCK":    C_YELLOW,
    "NINJA":   C_GRAY,
    "MESON":   C_CYAN,
    "ANT":     C_RED,
}


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET}  {msg}")

def err(msg: str) -> None:
    print(f"  {RED}✗{RESET}  {msg}")

def info(msg: str) -> None:
    print(f"  {BLUE}·{RESET}  {msg}")

def warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET}  {msg}")

def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")
    print(f"{DIM}{'─' * 48}{RESET}")
