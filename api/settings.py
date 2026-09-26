"""Server env flags. Read at call time so tests can patch os.environ."""

from __future__ import annotations

import os
from urllib.parse import urlencode


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def env_str(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def dev_login_enabled() -> bool:
    return env_flag("CASCADE_DEV_LOGIN")


def oauth_configured() -> bool:
    return bool(env_str("GITHUB_OAUTH_CLIENT_ID") and env_str("GITHUB_OAUTH_CLIENT_SECRET"))


def app_private_key_configured() -> bool:
    return bool(env_str("GITHUB_APP_PRIVATE_KEY", "GITHUB_APP_PRIVATE_KEY_PATH"))


def app_configured() -> bool:
    return bool(env_str("GITHUB_APP_ID") and app_private_key_configured())


def webhook_secret() -> str:
    return env_str("GITHUB_WEBHOOK_SECRET")


def app_slug() -> str:
    return env_str("GITHUB_APP_SLUG")


def app_install_url(state: str | None = None) -> str | None:
    slug = app_slug()
    if not slug:
        return None
    url = f"https://github.com/apps/{slug}/installations/new"
    if state:
        url = f"{url}?{urlencode({'state': state})}"
    return url


def session_secret() -> str:
    secret = env_str("SESSION_SECRET")
    if secret:
        return secret
    if dev_login_enabled():
        # ponytail: local harness only; production must set SESSION_SECRET.
        return "cascade-dev-insecure-session-secret"
    return ""


def public_base_url() -> str:
    return env_str("PUBLIC_BASE_URL").rstrip("/")


def cookie_secure(forwarded_proto: str, scheme: str) -> bool:
    explicit = env_str("CASCADE_COOKIE_SECURE")
    if explicit:
        return env_flag("CASCADE_COOKIE_SECURE")
    proto = (forwarded_proto or scheme or "").lower()
    return proto == "https"


def api_docs_enabled() -> bool:
    """Swagger/ReDoc/OpenAPI are opt-in so marketing /docs stays the product docs."""
    return env_flag("CASCADE_API_DOCS")
