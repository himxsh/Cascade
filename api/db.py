"""Thin DATABASE_URL layer. SQLite is the MVP driver; other URLs are recognized."""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  github_user_id INTEGER NOT NULL UNIQUE,
  login TEXT NOT NULL,
  avatar_url TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS installations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  installation_id INTEGER NOT NULL UNIQUE,
  account_login TEXT NOT NULL,
  account_type TEXT NOT NULL,
  installer_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  installation_id INTEGER NOT NULL REFERENCES installations(installation_id) ON DELETE CASCADE,
  owner TEXT NOT NULL,
  name TEXT NOT NULL,
  github_repo_id INTEGER NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  UNIQUE (installation_id, github_repo_id)
);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
  id TEXT PRIMARY KEY,
  event TEXT NOT NULL,
  action TEXT,
  repo_full_name TEXT,
  status TEXT NOT NULL,
  reason TEXT,
  received_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_repos_owner_name ON repos(owner, name);
CREATE INDEX IF NOT EXISTS idx_installations_installer ON installations(installer_user_id);
"""

_bootstrapped: set[str] = set()
_boot_lock = threading.Lock()


class UnsupportedDatabase(RuntimeError):
    """DATABASE_URL dialect is known but not wired in this iteration."""


def parse_database_url(url: str | None = None) -> tuple[str, str]:
    raw = (url if url is not None else os.environ.get("DATABASE_URL", "")).strip()
    if not raw:
        raw = f"sqlite:///{_default_sqlite_path()}"
    if raw.startswith("sqlite:////"):
        return "sqlite", raw[len("sqlite:///"):]
    if raw.startswith("sqlite:///"):
        return "sqlite", raw[len("sqlite:///"):]
    if raw.startswith("sqlite://"):
        rest = raw[len("sqlite://"):]
        return "sqlite", rest or _default_sqlite_path()
    if raw.startswith("file:"):
        return "sqlite", raw
    if raw.startswith("postgresql://") or raw.startswith("postgres://"):
        return "postgres", raw
    if raw.startswith("libsql://") or raw.startswith("turso://"):
        return "libsql", raw
    if "://" not in raw:
        return "sqlite", raw
    scheme = raw.split("://", 1)[0]
    raise UnsupportedDatabase(
        f"Unsupported DATABASE_URL scheme {scheme!r}. Use sqlite:///./cascade.db."
    )


def _default_sqlite_path() -> str:
    # ponytail: Vercel function fs is read-only except /tmp.
    if os.environ.get("VERCEL"):
        return "/tmp/cascade.db"
    return "./cascade.db"


def _sqlite_file(target: str) -> str:
    if target.startswith("file:") or target == ":memory:" or target.startswith(":memory:"):
        return target
    path = Path(target)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def connect(url: str | None = None) -> sqlite3.Connection:
    dialect, target = parse_database_url(url)
    if dialect != "sqlite":
        raise UnsupportedDatabase(
            f"DATABASE_URL dialect {dialect!r} is recognized but the driver "
            "is not wired yet. Use sqlite:///./cascade.db for this iteration."
        )
    path = _sqlite_file(target)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.Error:
        pass
    _ensure_schema(conn, path)
    return conn


def _ensure_schema(conn: sqlite3.Connection, key: str) -> None:
    with _boot_lock:
        if key in _bootstrapped:
            return
        conn.executescript(_SCHEMA)
        conn.commit()
        _bootstrapped.add(key)


def reset_bootstrap_cache() -> None:
    """Test helper — next connect() re-runs CREATE IF NOT EXISTS."""
    with _boot_lock:
        _bootstrapped.clear()


@contextmanager
def get_conn(url: str | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}
