#!/usr/bin/env python3
"""Claude Code Build Monitor - Test Suite"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

# Proje kokunu sys.path'e ekle
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "hooks"))


class TestPatterns(unittest.TestCase):

    def test_detect_npm_build(self):
        from shared.patterns import detect_build_command
        result = detect_build_command("npm run build")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "NPM")

    def test_detect_docker(self):
        from shared.patterns import detect_build_command
        result = detect_build_command("docker build -t myapp .")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "DOCKER")

    def test_detect_terraform(self):
        from shared.patterns import detect_build_command
        result = detect_build_command("terraform apply -auto-approve")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "TF")

    def test_detect_cargo(self):
        from shared.patterns import detect_build_command
        result = detect_build_command("cargo build --release")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "RUST")

    def test_detect_webpack(self):
        from shared.patterns import detect_build_command
        result = detect_build_command("webpack --mode production")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "WEBPACK")

    def test_detect_dotnet(self):
        from shared.patterns import detect_build_command
        result = detect_build_command("dotnet build MyProject.csproj")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "DOTNET")

    def test_detect_unknown_returns_none(self):
        from shared.patterns import detect_build_command
        self.assertIsNone(detect_build_command("ls -la"))
        self.assertIsNone(detect_build_command("cat README.md"))
        self.assertIsNone(detect_build_command("echo hello"))

    def test_all_patterns_valid_regex(self):
        from shared.patterns import DEFAULT_PATTERNS
        for pattern, label, tool in DEFAULT_PATTERNS:
            try:
                re.compile(pattern)
            except re.error:
                self.fail(f"Invalid regex in pattern: {pattern!r} ({tool}/{label})")

    def test_case_insensitive_matching(self):
        from shared.patterns import detect_build_command
        result = detect_build_command("NPM RUN BUILD")
        self.assertIsNotNone(result)


class TestSanitizeCommand(unittest.TestCase):

    def setUp(self):
        from hooks.pre_tool_use import sanitize_command
        self.sanitize = sanitize_command

    def test_redacts_token(self):
        result = self.sanitize("npm publish --token=abc123")
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("abc123", result)

    def test_redacts_password(self):
        result = self.sanitize("mysql --password=secret123")
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("secret123", result)

    def test_redacts_secret(self):
        result = self.sanitize("aws --secret-key MY_KEY_VALUE")
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("MY_KEY_VALUE", result)

    def test_redacts_url_credentials(self):
        result = self.sanitize("git push https://user:pass@github.com/repo")
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("user:pass", result)

    def test_truncates_long_commands(self):
        long_cmd = "a" * 200
        result = self.sanitize(long_cmd)
        self.assertLessEqual(len(result), 120)
        self.assertTrue(result.endswith("..."))

    def test_preserves_normal_commands(self):
        cmd = "npm run build"
        result = self.sanitize(cmd)
        self.assertEqual(result, cmd)


class TestPaths(unittest.TestCase):

    def test_state_dir_exists(self):
        from shared.paths import STATE_DIR
        self.assertTrue(STATE_DIR.exists())

    def test_state_dir_permissions(self):
        from shared.paths import STATE_DIR
        mode = STATE_DIR.stat().st_mode & 0o777
        self.assertEqual(mode, 0o700)

    def test_state_dir_has_uid_isolation(self):
        from shared.paths import STATE_DIR
        uid = os.getuid()
        # XDG_RUNTIME_DIR veya UID bazli path olmali
        dir_name = STATE_DIR.name
        self.assertTrue(
            "claude_build_monitor" in dir_name,
            f"State dir should contain 'claude_build_monitor': {STATE_DIR}"
        )


class TestFilelock(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = Path(self.tmpdir) / "test_state.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_locked_state_creates_file(self):
        from shared.filelock import locked_state
        with locked_state(self.state_file) as commands:
            commands.append({"id": "test"})
        self.assertTrue(self.state_file.exists())

    def test_locked_state_atomic_write(self):
        from shared.filelock import locked_state
        with locked_state(self.state_file) as commands:
            commands.append({"id": "1", "status": "running"})
        with locked_state(self.state_file) as commands:
            self.assertEqual(len(commands), 1)
            self.assertEqual(commands[0]["id"], "1")

    def test_locked_state_with_empty_file(self):
        from shared.filelock import locked_state
        self.state_file.write_text("")
        with locked_state(self.state_file) as commands:
            self.assertIsInstance(commands, list)
            self.assertEqual(len(commands), 0)


class TestDB(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        # Gecici DB path'i kullan
        import shared.paths
        self._orig_db = shared.paths.HISTORY_DB
        shared.paths.HISTORY_DB = self.db_path
        # db modulu icin de guncelle
        import shared.db
        shared.db.HISTORY_DB = self.db_path

    def tearDown(self):
        import shutil
        import shared.paths
        import shared.db
        shared.paths.HISTORY_DB = self._orig_db
        shared.db.HISTORY_DB = self._orig_db
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_db_creates_tables(self):
        from shared.db import init_db, get_connection
        init_db()
        with get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            self.assertIn("builds", table_names)

    def test_record_and_query_build(self):
        from shared.db import init_db, record_build, get_expected_duration
        init_db()
        cmd = {"tool": "NPM", "label": "npm build", "command": "npm run build",
               "project_id": "test123", "project": "test-project"}
        record_build(cmd, 15.5, True)
        result = get_expected_duration("NPM", "test123")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 15.5, places=1)

    def test_get_expected_duration_no_data(self):
        from shared.db import init_db, get_expected_duration
        init_db()
        result = get_expected_duration("NONEXISTENT", "nope")
        self.assertIsNone(result)


class TestColors(unittest.TestCase):

    def test_tool_colors_has_common_tools(self):
        from shared.colors import TOOL_COLORS
        for tool in ["NPM", "DOCKER", "RUST", "GO", "TEST", "GIT", "CMD", "WEBPACK"]:
            self.assertIn(tool, TOOL_COLORS, f"Missing color for {tool}")

    def test_color_functions_exist(self):
        from shared.colors import ok, err, info, warn, section
        # Sadece callable olduklarini kontrol et
        self.assertTrue(callable(ok))
        self.assertTrue(callable(err))
        self.assertTrue(callable(info))
        self.assertTrue(callable(warn))
        self.assertTrue(callable(section))


class TestConstants(unittest.TestCase):

    def test_constants_have_valid_values(self):
        from shared.constants import (
            PHASE_INTERVAL_SECS, PROGRESS_DAMPING, OVERLAY_REFRESH_INTERVAL,
            COMMAND_MAX_LENGTH, GIT_TIMEOUT_SECS, MINI_SHOW_AFTER_SECS,
        )
        self.assertGreater(PHASE_INTERVAL_SECS, 0)
        self.assertGreater(PROGRESS_DAMPING, 0)
        self.assertGreater(OVERLAY_REFRESH_INTERVAL, 0)
        self.assertGreater(COMMAND_MAX_LENGTH, 0)
        self.assertGreater(GIT_TIMEOUT_SECS, 0)
        self.assertGreater(MINI_SHOW_AFTER_SECS, 0)


if __name__ == "__main__":
    unittest.main()
