"""Users, sessions, installations, repos, webhook deliveries."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from api.db import row_to_dict

# GitHub installation ids are positive. Per-user mocks use -user_id (never 0).
MOCK_INSTALLATION_ID = 0

MOCK_REPOS = (
    {"github_repo_id": 1001, "owner": "acme", "name": "analytics", "enabled": 0},
    {"github_repo_id": 1002, "owner": "acme", "name": "metrics-dbt", "enabled": 0},
)

SESSION_TTL = timedelta(days=30)

DEV_GITHUB_USER_ID = 0
DEV_LOGIN = "dev"


class InstallationOwnershipError(Exception):
    """An installation already belongs to a different dashboard user."""

    def __init__(self, message: str = "installation belongs to another user"):
        super().__init__(message)
        self.message = message


def is_mock_installation_id(installation_id: int) -> bool:
    return int(installation_id) <= MOCK_INSTALLATION_ID


def mock_installation_id_for_user(user_id: int) -> int:
    """Stable, per-user mock id. GitHub installation ids are always positive."""
    uid = int(user_id)
    if uid <= 0:
        raise ValueError("user_id must be a positive users.id")
    return -uid


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def upsert_user(
    conn: Any,
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


def create_session(conn: Any, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    conn.execute(
        "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, _iso(now), _iso(now + SESSION_TTL)),
    )
    return token


def get_session_user(conn: Any, session_id: str | None) -> dict[str, Any] | None:
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


def delete_session(conn: Any, session_id: str | None) -> None:
    if not session_id:
        return
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def upsert_installation(
    conn: Any,
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
        owner_id = int(existing["installer_user_id"])
        if owner_id != int(installer_user_id):
            raise InstallationOwnershipError(
                "installation belongs to another user"
            )
        conn.execute(
            """
            UPDATE installations
            SET account_login = ?, account_type = ?
            WHERE installation_id = ?
            """,
            (account_login, account_type, installation_id),
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


def delete_installation(conn: Any, installation_id: int) -> None:
    conn.execute("DELETE FROM repos WHERE installation_id = ?", (installation_id,))
    conn.execute("DELETE FROM installations WHERE installation_id = ?", (installation_id,))


def list_installations_for_user(conn: Any, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM installations WHERE installer_user_id = ? ORDER BY installation_id",
        (user_id,),
    ).fetchall()
    return [row_to_dict(r) or {} for r in rows]


def seed_mock_workspace(conn: Any, user_id: int) -> dict[str, Any]:
    """Create a per-user mock install + repos so the dashboard works without a GitHub App."""
    existing = list_installations_for_user(conn, user_id)
    if existing:
        return existing[0]
    mock_id = mock_installation_id_for_user(user_id)
    inst = upsert_installation(
        conn,
        installation_id=mock_id,
        account_login="acme",
        account_type="Organization",
        installer_user_id=user_id,
    )
    seed_mock_repos(conn, mock_id)
    return inst


def seed_mock_repos(conn: Any, installation_id: int) -> list[dict[str, Any]]:
    for spec in MOCK_REPOS:
        found = conn.execute(
            """
            SELECT id FROM repos
            WHERE installation_id = ? AND github_repo_id = ?
            """,
            (installation_id, spec["github_repo_id"]),
        ).fetchone()
        if found:
            continue
        conn.execute(
            """
            INSERT INTO repos (
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


def _delete_mock_installations_for_user(conn: Any, user_id: int) -> None:
    rows = conn.execute(
        """
        SELECT installation_id FROM installations
        WHERE installer_user_id = ? AND installation_id <= 0
        """,
        (user_id,),
    ).fetchall()
    for row in rows:
        delete_installation(conn, int(row["installation_id"]))


def adopt_installation(
    conn: Any,
    *,
    user_id: int,
    installation_id: int,
    account_login: str = "unknown",
    account_type: str = "Organization",
) -> dict[str, Any]:
    if is_mock_installation_id(installation_id):
        raise InstallationOwnershipError("mock installation ids cannot be adopted from setup")
    _delete_mock_installations_for_user(conn, user_id)
    inst = upsert_installation(
        conn,
        installation_id=installation_id,
        account_login=account_login or "unknown",
        account_type=account_type or "Organization",
        installer_user_id=user_id,
    )
    seed_mock_repos(conn, installation_id)
    return inst


def list_repos_for_installation(conn: Any, installation_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM repos WHERE installation_id = ? ORDER BY owner, name",
        (installation_id,),
    ).fetchall()
    return [_repo_out(r) for r in rows]


def list_repos_for_user(conn: Any, user_id: int) -> list[dict[str, Any]]:
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


def _repo_out(row: Any) -> dict[str, Any]:
    data = row_to_dict(row) or {}
    data["enabled"] = bool(data.get("enabled"))
    data["full_name"] = f"{data.get('owner')}/{data.get('name')}"
    return data


def set_repo_enabled(
    conn: Any,
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
    conn: Any,
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
    conn: Any,
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
