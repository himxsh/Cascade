"""Thin FastAPI surface for the Cascade UI. Reuses cascade/* — no JS reimplementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

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

app = FastAPI(title="Cascade UI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    diff: str = Field(..., description="JSON changes or SQL/dbt unified diff")
    urn: str = DEFAULT_URN
    source: Literal["fixture", "live", "auto"] = "fixture"


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    gms_ok = health_check()
    return {"ok": True, "gms": gms_ok, "ui": (_STATIC / "index.html").is_file()}


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
    existing = _static_file(full_path)
    if existing is not None:
        return FileResponse(existing)
    return _index_html()
