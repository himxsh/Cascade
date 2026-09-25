"""Thin FastAPI surface for the Cascade UI. Reuses cascade/* — no JS reimplementation."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from api.auth import (
    COOKIE_NAME,
    AuthError,
    exchange_code,
    oauth_authorize_url,
    oauth_redirect_uri,
    unsign_payload,
)
from api.db import get_conn
from api.github_app import (
    GitHubAppError,
    fetch_installation,
    make_setup_state,
    setup_state_matches,
    user_may_claim_installation,
)
from api.settings import (
    app_configured,
    app_install_url,
    app_slug,
    cookie_secure,
    dev_login_enabled,
    env_str,
    oauth_configured,
    webhook_secret,
)
from api.store import (
    DEV_GITHUB_USER_ID,
    DEV_LOGIN,
    InstallationOwnershipError,
    adopt_installation,
    create_session,
    delete_session,
    get_session_user,
    is_mock_installation_id,
    list_installations_for_user,
    list_repos_for_user,
    lookup_repo,
    record_delivery,
    seed_mock_workspace,
    set_repo_enabled,
    upsert_user,
)
from api.webhook import (
    WebhookError,
    decide_event,
    log_decision,
    parse_json_body,
    repo_fields,
    verify_signature,
)
from cascade.datahub_live import health_check
from cascade.demo import DEFAULT_URN
from cascade.dotenv_load import load_dotenv
from cascade.ui_run import load_demo_diff, run_ui_pipeline

load_dotenv()

# Built UI lives next to the function so Vercel includes it in the bundle.
_STATIC = Path(__file__).resolve().parent / "static"

_STATIC_ROOT = _STATIC.resolve()

# Fallback if the built PNG did not land in the function bundle.
_FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">'
    '<rect width="32" height="32" fill="#050506"/>'
    '<path d="M6 24 L16 6 L26 24" stroke="#e4e8f0" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
    '<path d="M11 24 L16 14 L21 24" stroke="#fc3010" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
    "</svg>"
)

SESSION_COOKIE_MAX_AGE = 30 * 24 * 3600
APP_NOT_READY_BANNER = (
    "The Cascade GitHub App is not registered yet. Create it on your laptop "
    "(see Docs → GitHub App), then set GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, "
    "GITHUB_APP_SLUG, and GITHUB_WEBHOOK_SECRET. Until then this dashboard uses "
    "a mock repository list; workers will not comment as the App."
)


def _static_file(relative: str) -> Path | None:
    target = (_STATIC / relative).resolve()
    if str(target).startswith(str(_STATIC_ROOT)) and target.is_file():
        return target
    return None


def _index_html() -> FileResponse:
    index = _STATIC / "index.html"
    if not index.is_file():
        raise HTTPException(
            status_code=404,
            detail="UI bundle missing (api/static). Rebuild with scripts/vercel_build.py.",
        )
    return FileResponse(index)


def _favicon_response() -> FileResponse | Response:
    png = _static_file("favicon.png") or _static_file("logo.png")
    if png is not None:
        return FileResponse(
            png,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    return Response(
        content=_FAVICON_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _cors_origins() -> list[str]:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    extra = env_str("CORS_ORIGINS")
    if extra:
        origins.extend(item.strip() for item in extra.split(",") if item.strip())
    public = env_str("PUBLIC_BASE_URL").rstrip("/")
    if public:
        origins.append(public)
    return origins


app = FastAPI(title="Cascade UI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


class RunRequest(BaseModel):
    diff: str = Field(..., description="JSON changes or SQL/dbt unified diff")
    urn: str = DEFAULT_URN
    source: Literal["fixture", "live", "auto"] = "fixture"


class RepoPatch(BaseModel):
    id: int
    enabled: bool


def _cookie_kwargs(request: Request) -> dict[str, Any]:
    forwarded = request.headers.get("x-forwarded-proto", "")
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": cookie_secure(forwarded, request.url.scheme),
        "path": "/",
        "max_age": SESSION_COOKIE_MAX_AGE,
    }


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    kwargs = _cookie_kwargs(request)
    response.set_cookie(value=token, **kwargs)


def _clear_session_cookie(response: Response, request: Request) -> None:
    kwargs = _cookie_kwargs(request)
    kwargs.pop("max_age", None)
    response.delete_cookie(
        key=COOKIE_NAME,
        path=kwargs["path"],
        httponly=True,
        samesite="lax",
        secure=kwargs["secure"],
    )


def _current_user(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(COOKIE_NAME)
    with get_conn() as conn:
        return get_session_user(conn, token)


def _require_user(request: Request) -> dict[str, Any]:
    user = _current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


def _user_public(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "github_user_id": user["github_user_id"],
        "login": user["login"],
        "avatar_url": user["avatar_url"],
        "dev": int(user["github_user_id"]) == DEV_GITHUB_USER_ID,
    }


def _app_banner() -> str | None:
    if app_configured() and app_slug() and webhook_secret():
        return None
    return APP_NOT_READY_BANNER


def _safe_next(path: str | None) -> str:
    value = (path or "/app").strip() or "/app"
    if not value.startswith("/") or value.startswith("//"):
        return "/app"
    return value


def _login_and_redirect(request: Request, user_fields: dict[str, Any], next_path: str) -> RedirectResponse:
    with get_conn() as conn:
        user = upsert_user(conn, **user_fields)
        if not app_configured():
            seed_mock_workspace(conn, int(user["id"]))
        token = create_session(conn, int(user["id"]))
    response = RedirectResponse(_safe_next(next_path), status_code=302)
    _set_session_cookie(response, request, token)
    return response


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    db_ok = False
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    gms_ok = health_check()
    return {
        "ok": True,
        "gms": gms_ok,
        "ui": (_STATIC / "index.html").is_file(),
        "db": db_ok,
    }


@app.get("/api/demo-diff")
def api_demo_diff() -> dict[str, Any]:
    return load_demo_diff()


@app.post("/api/run")
def api_run(body: RunRequest) -> dict[str, Any]:
    if body.source == "live" and not health_check():
        raise HTTPException(
            status_code=503,
            detail="DataHub GMS is unreachable. Set DATAHUB_GMS_URL or use source=fixture.",
        )
    try:
        return run_ui_pipeline(
            diff_text=body.diff,
            urn=body.urn,
            source=body.source,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get("/api/auth/config")
def api_auth_config() -> dict[str, Any]:
    return {
        "oauth_configured": oauth_configured(),
        "dev_login": dev_login_enabled(),
        "app_configured": app_configured(),
        "app_slug": app_slug() or None,
        "app_install_url": app_install_url(),
        "webhook_configured": bool(webhook_secret()),
        "banner": _app_banner(),
    }


@app.get("/api/me")
def api_me(request: Request) -> dict[str, Any]:
    user = _require_user(request)
    with get_conn() as conn:
        installations = list_installations_for_user(conn, int(user["id"]))
        repos = list_repos_for_user(conn, int(user["id"]))
    try:
        install_url = app_install_url(make_setup_state(user))
    except AuthError:
        install_url = app_install_url()
    return {
        **_user_public(user),
        "installations": [
            {
                "installation_id": row["installation_id"],
                "account_login": row["account_login"],
                "account_type": row["account_type"],
            }
            for row in installations
        ],
        "repo_count": len(repos),
        "enabled_count": sum(1 for row in repos if row["enabled"]),
        "banner": _app_banner(),
        "app_install_url": install_url,
    }


@app.get("/api/repos")
def api_list_repos(request: Request) -> dict[str, Any]:
    user = _require_user(request)
    with get_conn() as conn:
        if not app_configured():
            seed_mock_workspace(conn, int(user["id"]))
        repos = list_repos_for_user(conn, int(user["id"]))
        installations = list_installations_for_user(conn, int(user["id"]))
    mock = (not app_configured()) or any(
        is_mock_installation_id(int(i["installation_id"])) for i in installations
    )
    return {
        "repos": repos,
        "mock": mock,
        "banner": _app_banner(),
        "installations": [
            {
                "installation_id": row["installation_id"],
                "account_login": row["account_login"],
                "account_type": row["account_type"],
            }
            for row in installations
        ],
    }


@app.patch("/api/repos")
def api_patch_repo(request: Request, body: RepoPatch) -> dict[str, Any]:
    user = _require_user(request)
    with get_conn() as conn:
        updated = set_repo_enabled(
            conn,
            user_id=int(user["id"]),
            repo_id=body.id,
            enabled=body.enabled,
        )
    if updated is None:
        raise HTTPException(status_code=404, detail="repo not found")
    return {"repo": updated}


@app.get("/api/github/setup")
def api_github_setup(
    request: Request,
    installation_id: int | None = None,
    setup_action: str | None = None,
    state: str | None = None,
    account_login: str | None = None,
    account_type: str | None = None,
) -> RedirectResponse:
    user = _current_user(request)
    next_q = str(request.url).split("?", 1)
    setup_url = "/api/github/setup" + (f"?{next_q[1]}" if len(next_q) == 2 else "")
    if user is None:
        return RedirectResponse(f"/signin?next={quote(setup_url, safe='')}", status_code=302)
    if installation_id is None:
        return RedirectResponse("/app/connect?error=missing_installation", status_code=302)
    if is_mock_installation_id(installation_id):
        return RedirectResponse("/app/connect?error=invalid_installation", status_code=302)

    claimed_login = account_login or "unknown"
    claimed_type = account_type or "Organization"
    state_ok = setup_state_matches(state, user)

    if app_configured():
        try:
            remote = fetch_installation(installation_id)
        except GitHubAppError:
            return RedirectResponse("/app/connect?error=installation_not_found", status_code=302)
        if not user_may_claim_installation(user, remote, state_ok=state_ok):
            return RedirectResponse("/app/connect?error=installation_forbidden", status_code=302)
        claimed_login = remote["account_login"]
        claimed_type = remote["account_type"]

    try:
        with get_conn() as conn:
            adopt_installation(
                conn,
                user_id=int(user["id"]),
                installation_id=installation_id,
                account_login=claimed_login,
                account_type=claimed_type,
            )
    except InstallationOwnershipError:
        return RedirectResponse("/app/connect?error=installation_owned", status_code=302)
    dest = "/app/repos?installed=1"
    if setup_action:
        dest += f"&setup_action={quote(setup_action)}"
    return RedirectResponse(dest, status_code=302)


@app.get("/auth/github")
def auth_github(request: Request, next: str = "/app") -> RedirectResponse:
    if not oauth_configured():
        if dev_login_enabled():
            return RedirectResponse("/signin?reason=oauth_unconfigured", status_code=302)
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")
    try:
        redirect_uri = oauth_redirect_uri(str(request.base_url).rstrip("/"))
        url = oauth_authorize_url(redirect_uri=redirect_uri, next_path=_safe_next(next))
    except AuthError as e:
        raise HTTPException(status_code=e.status, detail=e.message) from e
    return RedirectResponse(url, status_code=302)


@app.get("/auth/github/callback")
def auth_github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        return RedirectResponse(f"/signin?reason={quote(error)}", status_code=302)
    if not code or not state:
        return RedirectResponse("/signin?reason=missing_code", status_code=302)
    try:
        payload = unsign_payload(state)
        redirect_uri = oauth_redirect_uri(str(request.base_url).rstrip("/"))
        gh_user = exchange_code(code, redirect_uri)
    except AuthError as e:
        return RedirectResponse(f"/signin?reason={quote(e.message)}", status_code=302)
    return _login_and_redirect(request, gh_user, str(payload.get("next") or "/app"))


@app.get("/auth/dev-login")
def auth_dev_login(request: Request, next: str = "/app") -> RedirectResponse:
    if not dev_login_enabled():
        raise HTTPException(status_code=404, detail="dev login is disabled")
    return _login_and_redirect(
        request,
        {
            "github_user_id": DEV_GITHUB_USER_ID,
            "login": DEV_LOGIN,
            "avatar_url": "",
        },
        next,
    )


@app.get("/auth/logout")
def auth_logout(request: Request) -> RedirectResponse:
    token = request.cookies.get(COOKIE_NAME)
    with get_conn() as conn:
        delete_session(conn, token)
    response = RedirectResponse("/", status_code=302)
    _clear_session_cookie(response, request)
    return response


@app.post("/api/github/webhook")
async def api_github_webhook(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        verify_signature(raw, request.headers.get("x-hub-signature-256"))
        payload = parse_json_body(raw)
    except WebhookError as e:
        return JSONResponse({"ok": False, "detail": e.message}, status_code=e.status)

    event = (request.headers.get("x-github-event") or "").strip() or "unknown"
    header_delivery = (request.headers.get("x-github-delivery") or "").strip()
    delivery_id = header_delivery or f"local-{uuid.uuid4()}"

    with get_conn() as conn:
        if header_delivery:
            inserted = record_delivery(
                conn,
                delivery_id=delivery_id,
                event=event,
                action=str(payload.get("action") or "") or None,
                repo_full_name=None,
                status="received",
                reason=None,
            )
            if not inserted:
                return JSONResponse(
                    {"ok": True, "status": "duplicate", "delivery_id": delivery_id, "comment": False},
                    status_code=200,
                )

        _, owner, name, github_repo_id = repo_fields(payload)
        row = lookup_repo(conn, owner=owner, name=name, github_repo_id=github_repo_id)
        enabled = None if row is None else bool(row["enabled"])
        decision = decide_event(event, payload, repo_enabled=enabled)
        log_decision(decision, delivery_id=delivery_id)
        if header_delivery:
            conn.execute(
                """
                UPDATE webhook_deliveries
                SET action = ?, repo_full_name = ?, status = ?, reason = ?
                WHERE id = ?
                """,
                (
                    decision.get("action"),
                    decision.get("repo"),
                    str(decision.get("status") or "skipped"),
                    decision.get("reason"),
                    delivery_id,
                ),
            )
        else:
            record_delivery(
                conn,
                delivery_id=delivery_id,
                event=event,
                action=decision.get("action"),
                repo_full_name=decision.get("repo"),
                status=str(decision.get("status") or "skipped"),
                reason=decision.get("reason"),
            )

    # Phase 7: mint installation token and comment. Not in this iteration.
    return JSONResponse(
        {
            "ok": True,
            "delivery_id": delivery_id,
            "status": decision["status"],
            "reason": decision["reason"],
            "event": decision["event"],
            "action": decision["action"],
            "repo": decision["repo"],
            "queued": decision["queued"],
            "comment": False,
        },
        status_code=200,
    )


@app.get("/")
def spa_index() -> FileResponse:
    return _index_html()


@app.api_route("/favicon.svg", methods=["GET", "HEAD"], response_model=None)
def spa_favicon_svg() -> Response:
    svg = _static_file("favicon.svg")
    if svg is not None:
        return FileResponse(svg, media_type="image/svg+xml")
    return _favicon_response()


@app.api_route("/favicon.ico", methods=["GET", "HEAD"], response_model=None)
def spa_favicon_ico() -> Response:
    return _favicon_response()


@app.get("/assets/{asset_path:path}")
def spa_asset(asset_path: str) -> FileResponse:
    # ponytail: path traversal guard; assets are hashed build outputs only
    target = _static_file(f"assets/{asset_path}")
    if target is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(target)


@app.get("/{full_path:path}")
def spa_fallback(full_path: str) -> FileResponse:
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="not found")
    if full_path == "auth" or full_path.startswith("auth/"):
        raise HTTPException(status_code=404, detail="not found")
    existing = _static_file(full_path)
    if existing is not None:
        return FileResponse(existing)
    return _index_html()
