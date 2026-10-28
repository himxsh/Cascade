"""GitHub App JWT + installation lookup. Does not mint installation tokens (Phase 7)."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from typing import Any

from api.auth import AuthError, sign_payload, unsign_payload
from api.settings import env_str

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
except ImportError:  # pragma: no cover — optional until `[ui]` / hosted extras install
    default_backend = None  # type: ignore[assignment]
    hashes = None  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]
    padding = None  # type: ignore[assignment]

GITHUB_API = "https://api.github.com"
USER_AGENT = "cascade-bot"
SETUP_STATE_MAX_AGE_SEC = 86400
SETUP_STATE_PURPOSE = "github_setup"


class GitHubAppError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def make_setup_state(user: dict[str, Any]) -> str:
    return sign_payload(
        {
            "ts": int(time.time()),
            "purpose": SETUP_STATE_PURPOSE,
            "user_id": int(user["id"]),
            "github_user_id": int(user["github_user_id"]),
        }
    )


def setup_state_matches(state: str | None, user: dict[str, Any]) -> bool:
    if not state:
        return False
    try:
        payload = unsign_payload(state, max_age=SETUP_STATE_MAX_AGE_SEC)
    except AuthError:
        return False
    if payload.get("purpose") != SETUP_STATE_PURPOSE:
        return False
    try:
        return int(payload.get("user_id") or 0) == int(user["id"])
    except (TypeError, ValueError):
        return False


def load_private_key_pem() -> bytes:
    raw = env_str("GITHUB_APP_PRIVATE_KEY")
    if raw:
        return raw.replace("\\n", "\n").encode()
    path = env_str("GITHUB_APP_PRIVATE_KEY_PATH")
    if path:
        with open(path, "rb") as handle:
            return handle.read()
    raise GitHubAppError("GITHUB_APP_PRIVATE_KEY is not set", status=503)


def create_app_jwt() -> str:
    if serialization is None or padding is None or hashes is None or default_backend is None:
        raise GitHubAppError(
            "cryptography is required to verify GitHub App installations",
            status=503,
        )

    app_id = env_str("GITHUB_APP_ID")
    if not app_id:
        raise GitHubAppError("GITHUB_APP_ID is not set", status=503)
    pem = load_private_key_pem()
    try:
        key = serialization.load_pem_private_key(pem, password=None, backend=default_backend())
    except ValueError as e:
        raise GitHubAppError("GITHUB_APP_PRIVATE_KEY is not a valid PEM", status=503) from e

    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64url(
        json.dumps(
            {"iat": now - 60, "exp": now + 540, "iss": app_id},
            separators=(",", ":"),
        ).encode()
    )
    message = f"{header}.{body}".encode()
    if not hasattr(key, "sign"):
        raise GitHubAppError("GITHUB_APP_PRIVATE_KEY must be an RSA private key", status=503)
    signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{body}.{_b64url(signature)}"


def fetch_installation(installation_id: int) -> dict[str, Any]:
    """GET /app/installations/{id} using an App JWT. Confirms the id exists on GitHub."""
    token = create_app_jwt()
    data = _http_json(
        f"{GITHUB_API}/app/installations/{int(installation_id)}",
        token=token,
    )
    account = data.get("account") or {}
    login = str(account.get("login") or "").strip()
    if not login:
        raise GitHubAppError("GitHub installation payload missing account.login")
    account_id = account.get("id")
    return {
        "installation_id": int(data.get("id") or installation_id),
        "account_login": login,
        "account_type": str(account.get("type") or "Organization"),
        "account_id": int(account_id) if isinstance(account_id, int) else None,
        "target_type": str(data.get("target_type") or account.get("type") or ""),
    }


def user_may_claim_installation(
    user: dict[str, Any],
    remote: dict[str, Any],
    *,
    state_ok: bool,
    accessible_ids: set[int] | None = None,
) -> bool:
    """Personal installs must match the signed-in GitHub user.

    Org installs must be in that user's installation list (from their OAuth
    token) and carry the signed setup state. State alone is not authorization:
    any signed-in user can mint one from /api/me and pair it with another
    installation_id.
    """
    account_type = str(remote.get("account_type") or remote.get("target_type") or "")
    account_id = remote.get("account_id")
    if account_type.lower() == "user" and account_id is not None:
        try:
            if int(account_id) == int(user["github_user_id"]):
                return True
        except (TypeError, ValueError):
            return False
    try:
        inst_id = int(remote["installation_id"])
    except (KeyError, TypeError, ValueError):
        return False
    allowed = accessible_ids or set()
    return bool(state_ok and inst_id in allowed)


def list_accessible_installation_ids(user_token: str) -> set[int]:
    """Installation ids visible to this GitHub App user access token."""
    found: set[int] = set()
    for page in range(1, 11):
        data = _http_json(
            f"{GITHUB_API}/user/installations?per_page=100&page={page}",
            token=user_token,
        )
        rows = data.get("installations") or []
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("id"), int):
                found.add(int(row["id"]))
        if len(rows) < 100:
            break
    return found


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _http_json(url: str, *, token: str) -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        status = 404 if e.code == 404 else 502
        raise GitHubAppError(
            f"GitHub installation lookup failed ({e.code}): {detail}",
            status=status,
        ) from e
    except urllib.error.URLError as e:
        raise GitHubAppError(f"GitHub unreachable: {e.reason}") from e
    if not isinstance(payload, dict):
        raise GitHubAppError("GitHub installation payload must be an object")
    return payload
