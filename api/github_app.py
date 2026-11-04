"""GitHub App authentication and setup pull requests for consumer workflows."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from cascade.workflow import render_workflow

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
    def __init__(self, message: str, status: int = 502, github_status: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.github_status = github_status


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


def create_installation_token(installation_id: int) -> str:
    data = _http_json(
        f"{GITHUB_API}/app/installations/{int(installation_id)}/access_tokens",
        token=create_app_jwt(),
        method="POST",
        body={},
    )
    token = str(data.get("token") or "")
    if not token:
        raise GitHubAppError("GitHub response missing installation token")
    return token


def install_workflow(token: str, full_name: str) -> dict[str, Any]:
    owner, repo = full_name.split("/", 1)
    root = f"{GITHUB_API}/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
    repository = _http_json(root, token=token)
    base = str(repository.get("default_branch") or "main")
    path = ".github/workflows/cascade.yml"
    rendered = render_workflow()
    encoded = base64.b64encode(rendered.encode()).decode()
    try:
        _http_json(f"{root}/contents/{path}?ref={quote(base, safe='')}", token=token)
        return {"status": "exists"}
    except GitHubAppError as e:
        if e.github_status != 404:
            raise
    try:
        _http_json(f"{root}/contents/{path}", token=token, method="PUT", body={"message": "Add Cascade workflow", "content": encoded, "branch": base})
        return {"status": "committed"}
    except GitHubAppError as e:
        if e.github_status not in {403, 409, 422}:
            raise
    try:
        head = _http_json(f"{root}/git/ref/heads/{quote(base, safe='')}", token=token)
        sha = str((head.get("object") or {}).get("sha") or "")
        if not sha:
            raise GitHubAppError("GitHub response missing default branch sha")
        _http_json(f"{root}/git/ref/heads/cascade/setup", token=token)
        return {"status": "exists"}
    except GitHubAppError as e:
        if e.github_status != 404:
            raise
    prs = _http_json(f"{root}/pulls?state=open&head={quote(owner + ':cascade/setup', safe=':')}", token=token)
    if prs:
        return {"status": "exists"}
    _http_json(f"{root}/git/refs", token=token, method="POST", body={"ref": "refs/heads/cascade/setup", "sha": sha})
    _http_json(f"{root}/contents/{path}", token=token, method="PUT", body={"message": "Add Cascade workflow", "content": encoded, "branch": "cascade/setup"})
    body = (f"Add the Actions secret [LLM_API_KEY](https://github.com/{full_name}/settings/secrets/actions/new?name=LLM_API_KEY), "
            "and add DATAHUB_GMS_URL as an Actions secret. Set repo variables CASCADE_MODE and LLM_MODEL "
            f"in [Actions variables](https://github.com/{full_name}/settings/variables/actions). Your LLM key stays in your GitHub secrets.")
    _http_json(f"{root}/pulls", token=token, method="POST", body={"title": "Add Cascade GitHub Actions workflow", "head": "cascade/setup", "base": base, "body": body})
    return {"status": "pr_opened"}


def user_may_claim_installation(
    user: dict[str, Any],
    remote: dict[str, Any],
    *,
    state_ok: bool,
    org_admin: Callable[[str], bool] | None = None,
) -> bool:
    """Personal installs must match the signed-in GitHub user.

    Org installs need the signed setup state and an active admin membership in
    that org (checked lazily through `org_admin`). State alone is not
    authorization: any signed-in user can mint one from /api/me and pair it
    with another installation_id.
    """
    account_type = str(remote.get("account_type") or remote.get("target_type") or "")
    if account_type.lower() == "user":
        try:
            return int(remote["account_id"]) == int(user["github_user_id"])
        except (KeyError, TypeError, ValueError):
            return False
    login = str(remote.get("account_login") or "")
    if not state_ok or not login or org_admin is None:
        return False
    return bool(org_admin(login))


def user_is_org_admin(user_token: str, org_login: str) -> bool:
    """True when the OAuth user is an active admin of `org_login` (needs read:org)."""
    try:
        data = _http_json(
            f"{GITHUB_API}/user/memberships/orgs/{quote(org_login, safe='')}",
            token=user_token,
        )
    except GitHubAppError as e:
        if e.github_status == 404:
            return False
        raise
    return data.get("state") == "active" and data.get("role") == "admin"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _http_json(url: str, *, token: str, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, headers=headers, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        status = 404 if e.code == 404 else 502
        raise GitHubAppError(
            f"GitHub API request failed ({e.code}): {detail}",
            status=status,
            github_status=e.code,
        ) from e
    except urllib.error.URLError as e:
        raise GitHubAppError(f"GitHub unreachable: {e.reason}") from e
    if not isinstance(payload, (dict, list)):
        raise GitHubAppError("GitHub API payload must be an object or array")
    return payload
