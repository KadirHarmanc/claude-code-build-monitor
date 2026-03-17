# Claude Code Build Monitor

Real-time progress bars for build commands in Claude Code. Automatically detects 50+ build tools, shows animated TUI progress, plays notification sounds, and tracks build history with SQLite.

```
  ⠹  [NPM]  my-project  npm build  Linking modules
     ████████████████░░░░░░░░░░  62%  14s  ETA 8s
     $ npm run build
     ──────────────────────────────────────────
```

## Features

- **Auto-detection** — Recognizes 50+ build tools via regex patterns (npm, yarn, docker, terraform, k8s, cargo, go, and more)
- **Real-time TUI** — Animated progress bar with spinner, phase text, ETA, and elapsed time
- **Parallel builds** — Track multiple concurrent build commands simultaneously
- **Smart ETA** — Estimates completion time based on SQLite history of previous builds
- **Sound notifications** — Plays system sounds on build success/failure with full customization
- **Native OS notifications** — macOS (osascript) and Linux (notify-send) desktop alerts
- **Build history** — SQLite database tracks all builds with duration, success rate, and project context
- **CLI tool** — `claude-monitor` for managing patterns, sounds, history, and stats
- **Security hardened** — UID-isolated temp dirs, AppleScript injection prevention, credential redaction
- **Zero dependencies** — Pure Python 3.8+ stdlib, no pip install needed

## Supported Tools

| Category | Tools |
|----------|-------|
| Package Managers | npm, yarn, pnpm, bun |
| Monorepo | nx, turbo, lerna |
| Containers | docker, docker-compose |
| Deploy | vercel, netlify, fly, cloudflare, aws, gcloud, heroku, railway, render |
| IaC | terraform, pulumi, ansible, kubectl, helm |
| Build | cargo, go, make, cmake, gradle, maven, swift, xcodebuild |
| Python | pip, poetry, uv |
| Test | jest, pytest, vitest, mocha, playwright, cypress, go test, cargo test |
| VCS | git push |

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/claude-code-build-monitor.git
cd claude-code-build-monitor
python3 install.py
```

Restart Claude Code. That's it — next time Claude runs a build command, you'll see the progress bar.

## How It Works

```
Claude Code runs "npm run build"
        |
        v
PreToolUse Hook (pre_tool_use.py)
  - Detects build command via regex patterns
  - Looks up project context (git remote, package.json)
  - Queries SQLite for expected duration
  - Writes command to state file (with file locking)
  - Launches overlay process
        |
        v
TUI Overlay (overlay.py)
  - Reads state file every 100ms (mtime-optimized)
  - Renders animated progress bar to stderr
  - Shows phase text, ETA, spinner, elapsed time
  - Handles terminal resize (SIGWINCH)
        |
        v
PostToolUse Hook (post_tool_use.py)
  - Parses exit code from tool response
  - Records build duration to SQLite
  - Sends native OS notification
  - Plays notification sound
  - Stops overlay if no commands running
```

## Architecture

```
claude-code-build-monitor/
  hooks/
    pre_tool_use.py      # PreToolUse hook — detect & start tracking
    post_tool_use.py     # PostToolUse hook — record & notify
    overlay.py           # TUI progress bar renderer
  shared/
    paths.py             # Secure UID-isolated temp paths
    logging.py           # Centralized logging
    colors.py            # ANSI colors with TTY detection
    constants.py         # Configurable constants
    db.py                # SQLite with WAL mode
    filelock.py          # Atomic file locking (fcntl)
    patterns.py          # Build command patterns + custom patterns
  claude-monitor         # CLI management tool
  install.py             # One-command installer
```

## CLI Usage

```bash
# Installation
claude-monitor install        # Install hooks and CLI
claude-monitor uninstall      # Remove everything
claude-monitor status         # Check installation status

# Build History
claude-monitor history                    # Last 20 builds
claude-monitor history --tool NPM         # Filter by tool
claude-monitor history --limit 50         # More results
claude-monitor stats                      # Build statistics per tool

# Pattern Management
claude-monitor test-pattern "npm run build"   # Test if a command matches
claude-monitor list-patterns                   # Show all patterns
claude-monitor add-pattern '\bmytool\b' 'my tool' 'MYTOOL'  # Add custom

# Sound Management
claude-monitor sound list              # List all available sounds
claude-monitor sound discover          # Auto-discover system sounds
claude-monitor sound add alarm ~/a.mp3 # Add custom sound
claude-monitor sound remove alarm      # Remove a sound
claude-monitor sound set-success Pop   # Set success sound
claude-monitor sound set-failure Basso # Set failure sound
claude-monitor sound test Pop          # Preview a sound
claude-monitor sound on                # Enable sounds
claude-monitor sound off               # Disable sounds

# Configuration
claude-monitor config sound none              # Disable via env
claude-monitor config phase-interval 10       # Phase transition seconds
claude-monitor config disable 1               # Disable monitor
claude-monitor config log ~/monitor.log       # Enable debug logging
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_MONITOR_DISABLE` | Set to `1` to disable | (not set) |
| `CLAUDE_MONITOR_SOUND` | Custom sound path or `none` | system default |
| `CLAUDE_MONITOR_LOG` | Debug log file path | (not set) |
| `CLAUDE_MONITOR_PHASE_INTERVAL` | Seconds between phase changes | `8` |

### Custom Build Patterns

Add your own patterns via CLI:

```bash
claude-monitor add-pattern '\bmycli\s+build\b' 'mycli build' 'MYCLI'
```

Patterns are saved to `~/.claude/monitor_patterns.json` and loaded automatically. Custom patterns take priority over built-in ones.

### Sound Configuration

Sounds are configured in `~/.claude/monitor_sounds.json`:

```json
{
  "active_success": "Tink",
  "active_failure": "Basso",
  "custom_sounds": [
    {"name": "Tink", "path": "/System/Library/Sounds/Tink.aiff"},
    {"name": "Basso", "path": "/System/Library/Sounds/Basso.aiff"}
  ],
  "enabled": true
}
```

Priority order: `CLAUDE_MONITOR_SOUND` env var > `monitor_sounds.json` > system defaults.

## Requirements

- Python 3.8+
- Claude Code CLI
- macOS or Linux (Windows not yet supported)
- No external Python packages required

## Security

- **Isolated temp directory** — State files use UID-based paths (`/tmp/claude_build_monitor_<uid>/`) with `0o700` permissions, preventing other users from tampering
- **AppleScript injection prevention** — Notification text is escaped before passing to `osascript`
- **Credential redaction** — Commands containing `--token`, `--password`, `--secret`, `--key`, or URL credentials are automatically masked before storage
- **Atomic file writes** — State files use `fcntl.flock` + write-to-tmp-then-rename to prevent corruption from concurrent access

## Uninstall

```bash
claude-monitor uninstall
```

This removes hook files, shared modules, CLI binary, and cleans up `settings.json`. Build history (`~/.claude/build_history.db`) is preserved — delete it manually if desired.

## Contributing

Contributions are welcome! Some ideas:

- Windows support
- More build tool patterns
- Custom progress bar themes
- Webhook notifications (Slack, Discord)
- Build time trend graphs

## License

MIT License. See [LICENSE](LICENSE) for details.
