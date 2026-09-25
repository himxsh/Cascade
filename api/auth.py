"""OAuth state, session cookies, GitHub user lookup. No FastAPI imports."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from api.settings import env_str, oauth_configured, public_base_url, session_secret

GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_USER = "https://api.github.com/user"
COOKIE_NAME = "cascade_session"
STATE_MAX_AGE_SEC = 600
USER_AGENT = "cascade-bot"


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status
        self.message = message


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def sign_payload(payload: dict[str, Any]) -> str:
    secret = session_secret()
    if not secret:
        raise AuthError("SESSION_SECRET is not set", status=500)
    body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def unsign_payload(token: str, max_age: int = STATE_MAX_AGE_SEC) -> dict[str, Any]:
    secret = session_secret()
    if not secret:
        raise AuthError("SESSION_SECRET is not set", status=500)
    if "." not in token:
        raise AuthError("invalid state", status=400)
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise AuthError("invalid state", status=400)
    try:
        payload = json.loads(_b64url_decode(body).decode())
    except (ValueError, json.JSONDecodeError) as e:
        raise AuthError("invalid state", status=400) from e
    ts = int(payload.get("ts") or 0)
    if abs(time.time() - ts) > max_age:
        raise AuthError("state expired", status=400)
    return payload


def oauth_authorize_url(*, redirect_uri: str, next_path: str = "/app") -> str:
    if not oauth_configured():
        raise AuthError("GitHub OAuth is not configured", status=503)
    state = sign_payload({"ts": int(time.time()), "next": next_path or "/app"})
    query = urllib.parse.urlencode(
        {
            "client_id": env_str("GITHUB_OAUTH_CLIENT_ID"),
            "redirect_uri": redirect_uri,
            "scope": "read:user",
            "state": state,
        }
    )
    return f"{GITHUB_AUTHORIZE}?{query}"


def oauth_redirect_uri(request_base: str) -> str:
    explicit = env_str("GITHUB_OAUTH_REDIRECT_URI")
    if explicit:
        return explicit
    base = public_base_url() or request_base.rstrip("/")
    return f"{base}/auth/github/callback"


def _http_json(
    url: str,
    *,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        raise AuthError(f"GitHub API error ({e.code}): {detail}", status=502) from e
    except urllib.error.URLError as e:
        raise AuthError(f"GitHub unreachable: {e.reason}", status=502) from e


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    token_payload = _http_json(
        GITHUB_TOKEN,
        method="POST",
        data={
            "client_id": env_str("GITHUB_OAUTH_CLIENT_ID"),
            "client_secret": env_str("GITHUB_OAUTH_CLIENT_SECRET"),
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    access = token_payload.get("access_token")
    if not access:
        raise AuthError("GitHub did not return an access token", status=502)
    user = _http_json(GITHUB_USER, token=str(access))
    login = str(user.get("login") or "").strip()
    github_id = user.get("id")
    if not login or github_id is None:
        raise AuthError("GitHub user payload missing login/id", status=502)
    return {
        "github_user_id": int(github_id),
        "login": login,
        "avatar_url": str(user.get("avatar_url") or ""),
    }
