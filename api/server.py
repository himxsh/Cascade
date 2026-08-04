"""Thin FastAPI surface for the Cascade UI. Reuses cascade/* — no JS reimplementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from cascade.datahub_live import health_check
from cascade.demo import DEFAULT_URN
from cascade.ui_run import load_demo_diff, run_ui_pipeline

# Built UI lives next to the function so Vercel includes it in the bundle.
_STATIC = Path(__file__).resolve().parent / "static"

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
    index = _STATIC / "index.html"
    if not index.is_file():
        raise HTTPException(
            status_code=404,
            detail="UI bundle missing (api/static). Rebuild with scripts/vercel_build.py.",
        )
    return FileResponse(index)


@app.get("/favicon.svg")
def spa_favicon() -> FileResponse:
    path = _STATIC / "favicon.svg"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="favicon not found")
    return FileResponse(path)


@app.get("/assets/{asset_path:path}")
def spa_asset(asset_path: str) -> FileResponse:
    # ponytail: path traversal guard; assets are hashed build outputs only
    root = (_STATIC / "assets").resolve()
    target = (root / asset_path).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(target)
