"""Users, sessions, installations, repos, webhook deliveries."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from api.db import row_to_dict

# GitHub installation ids are positive. 0 is the local mock until the App exists.
MOCK_INSTALLATION_ID = 0

MOCK_REPOS = (
    {"github_repo_id": 1001, "owner": "acme", "name": "analytics", "enabled": 0},
    {"github_repo_id": 1002, "owner": "acme", "name": "metrics-dbt", "enabled": 0},
)

SESSION_TTL = timedelta(days=30)

DEV_GITHUB_USER_ID = 0
DEV_LOGIN = "dev"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def upsert_user(
    conn: sqlite3.Connection,
    *,
    github_user_id: int,
    login: str,
    avatar_url: str = "",
) -> dict[str, Any]:
    existing = conn.execute(
        "SELECT * FROM users WHERE github_user_id = ?",
        (github_user_id,),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE users SET login = ?, avatar_url = ? WHERE id = ?",
            (login, avatar_url, existing["id"]),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (existing["id"],)).fetchone()
        return row_to_dict(row) or {}
    conn.execute(
        "INSERT INTO users (github_user_id, login, avatar_url, created_at) VALUES (?, ?, ?, ?)",
        (github_user_id, login, avatar_url, _iso(_now())),
    )
    row = conn.execute(
        "SELECT * FROM users WHERE github_user_id = ?",
        (github_user_id,),
    ).fetchone()
    return row_to_dict(row) or {}


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    conn.execute(
        "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, _iso(now), _iso(now + SESSION_TTL)),
    )
    return token


def get_session_user(conn: sqlite3.Connection, session_id: str | None) -> dict[str, Any] | None:
    if not session_id:
        return None
    row = conn.execute(
        """
        SELECT u.* FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.id = ? AND s.expires_at > ?
        """,
        (session_id, _iso(_now())),
    ).fetchone()
    return row_to_dict(row)


def delete_session(conn: sqlite3.Connection, session_id: str | None) -> None:
    if not session_id:
        return
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def upsert_installation(
    conn: sqlite3.Connection,
    *,
    installation_id: int,
    account_login: str,
    account_type: str,
    installer_user_id: int,
) -> dict[str, Any]:
    existing = conn.execute(
        "SELECT * FROM installations WHERE installation_id = ?",
        (installation_id,),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE installations
            SET account_login = ?, account_type = ?, installer_user_id = ?
            WHERE installation_id = ?
            """,
            (account_login, account_type, installer_user_id, installation_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO installations (
              installation_id, account_login, account_type, installer_user_id, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (installation_id, account_login, account_type, installer_user_id, _iso(_now())),
        )
    row = conn.execute(
        "SELECT * FROM installations WHERE installation_id = ?",
        (installation_id,),
    ).fetchone()
    return row_to_dict(row) or {}


def delete_installation(conn: sqlite3.Connection, installation_id: int) -> None:
    conn.execute("DELETE FROM repos WHERE installation_id = ?", (installation_id,))
    conn.execute("DELETE FROM installations WHERE installation_id = ?", (installation_id,))


def list_installations_for_user(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM installations WHERE installer_user_id = ? ORDER BY installation_id",
        (user_id,),
    ).fetchall()
    return [row_to_dict(r) or {} for r in rows]


def seed_mock_workspace(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    """Create a mock install + repos so the dashboard can be used without a GitHub App."""
    existing = list_installations_for_user(conn, user_id)
    if existing:
        return existing[0]
    inst = upsert_installation(
        conn,
        installation_id=MOCK_INSTALLATION_ID,
        account_login="acme",
        account_type="Organization",
        installer_user_id=user_id,
    )
    seed_mock_repos(conn, MOCK_INSTALLATION_ID)
    return inst


def seed_mock_repos(conn: sqlite3.Connection, installation_id: int) -> list[dict[str, Any]]:
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM repos WHERE installation_id = ?",
        (installation_id,),
    ).fetchone()
    if count and int(count["n"]) > 0:
        return list_repos_for_installation(conn, installation_id)
    for spec in MOCK_REPOS:
        conn.execute(
            """
            INSERT OR IGNORE INTO repos (
              installation_id, owner, name, github_repo_id, enabled
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                installation_id,
                spec["owner"],
                spec["name"],
                spec["github_repo_id"],
                spec["enabled"],
            ),
        )
    return list_repos_for_installation(conn, installation_id)


def adopt_installation(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    installation_id: int,
    account_login: str = "unknown",
    account_type: str = "Organization",
) -> dict[str, Any]:
    if installation_id != MOCK_INSTALLATION_ID:
        mock = conn.execute(
            """
            SELECT installation_id FROM installations
            WHERE installer_user_id = ? AND installation_id = ?
            """,
            (user_id, MOCK_INSTALLATION_ID),
        ).fetchone()
        if mock:
            delete_installation(conn, MOCK_INSTALLATION_ID)
    inst = upsert_installation(
        conn,
        installation_id=installation_id,
        account_login=account_login or "unknown",
        account_type=account_type or "Organization",
        installer_user_id=user_id,
    )
    seed_mock_repos(conn, installation_id)
    return inst


def list_repos_for_installation(conn: sqlite3.Connection, installation_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM repos WHERE installation_id = ? ORDER BY owner, name",
        (installation_id,),
    ).fetchall()
    return [_repo_out(r) for r in rows]


def list_repos_for_user(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT r.* FROM repos r
        JOIN installations i ON i.installation_id = r.installation_id
        WHERE i.installer_user_id = ?
        ORDER BY r.owner, r.name
        """,
        (user_id,),
    ).fetchall()
    return [_repo_out(r) for r in rows]


def _repo_out(row: sqlite3.Row) -> dict[str, Any]:
    data = row_to_dict(row) or {}
    data["enabled"] = bool(data.get("enabled"))
    data["full_name"] = f"{data.get('owner')}/{data.get('name')}"
    return data


def set_repo_enabled(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    repo_id: int,
    enabled: bool,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT r.* FROM repos r
        JOIN installations i ON i.installation_id = r.installation_id
        WHERE r.id = ? AND i.installer_user_id = ?
        """,
        (repo_id, user_id),
    ).fetchone()
    if row is None:
        return None
    conn.execute("UPDATE repos SET enabled = ? WHERE id = ?", (1 if enabled else 0, repo_id))
    updated = conn.execute("SELECT * FROM repos WHERE id = ?", (repo_id,)).fetchone()
    return _repo_out(updated) if updated else None


def lookup_repo(
    conn: sqlite3.Connection,
    *,
    owner: str | None,
    name: str | None,
    github_repo_id: int | None = None,
) -> dict[str, Any] | None:
    if github_repo_id is not None:
        row = conn.execute(
            "SELECT * FROM repos WHERE github_repo_id = ? ORDER BY enabled DESC LIMIT 1",
            (github_repo_id,),
        ).fetchone()
        if row:
            return _repo_out(row)
    if owner and name:
        row = conn.execute(
            """
            SELECT * FROM repos
            WHERE lower(owner) = lower(?) AND lower(name) = lower(?)
            ORDER BY enabled DESC LIMIT 1
            """,
            (owner, name),
        ).fetchone()
        if row:
            return _repo_out(row)
    return None


def record_delivery(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    event: str,
    action: str | None,
    repo_full_name: str | None,
    status: str,
    reason: str | None,
) -> bool:
    """Insert a webhook delivery. Returns False if this id was already stored."""
    existing = conn.execute(
        "SELECT id FROM webhook_deliveries WHERE id = ?",
        (delivery_id,),
    ).fetchone()
    if existing:
        return False
    conn.execute(
        """
        INSERT INTO webhook_deliveries (
          id, event, action, repo_full_name, status, reason, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (delivery_id, event, action, repo_full_name, status, reason, _iso(_now())),
    )
    return True
