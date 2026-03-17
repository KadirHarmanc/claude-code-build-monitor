"""Merkezi veritabani yonetimi - WAL mode, index, schema version."""
from __future__ import annotations

import sqlite3
from typing import Optional

from shared.paths import HISTORY_DB
from shared.logging import log


_SCHEMA_VERSION = 1


def get_connection() -> sqlite3.Connection:
    """WAL modlu, timeout'lu SQLite baglantisi."""
    HISTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(HISTORY_DB), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    return conn


def init_db() -> None:
    """Veritabani semasini olustur veya guncelle."""
    try:
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS builds (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool         TEXT NOT NULL,
                    label        TEXT NOT NULL,
                    command      TEXT NOT NULL,
                    project_id   TEXT,
                    project_name TEXT,
                    duration     REAL,
                    success      INTEGER,
                    timestamp    DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tp ON builds(tool, project_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ts ON builds(timestamp)"
            )
    except sqlite3.Error as e:
        log("DB", f"init error: {e}")


def get_expected_duration(tool: str, project_id: str) -> Optional[float]:
    """Son 10 basarili build'in ortalama suresini dondur."""
    if not HISTORY_DB.exists():
        return None
    try:
        with get_connection() as conn:
            row = conn.execute("""
                SELECT AVG(duration) FROM (
                    SELECT duration FROM builds
                    WHERE tool = ? AND project_id = ? AND success = 1
                    ORDER BY timestamp DESC LIMIT 10
                )
            """, (tool, project_id)).fetchone()
            val = row[0] if row else None
            return float(val) if val else None
    except sqlite3.Error:
        return None


def record_build(cmd: dict, duration: float, success: bool) -> None:
    """Build sonucunu veritabanina kaydet."""
    if not HISTORY_DB.exists():
        return
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO builds (tool, label, command, project_id, project_name, duration, success)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                cmd.get("tool"),
                cmd.get("label"),
                cmd.get("command"),
                cmd.get("project_id"),
                cmd.get("project"),
                duration,
                1 if success else 0,
            ))
        log("DB", f"recorded {cmd.get('tool')} duration={duration:.1f}s success={success}")
    except sqlite3.Error as e:
        log("DB", f"record error: {e}")
