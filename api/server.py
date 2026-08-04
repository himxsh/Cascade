"""Thin FastAPI surface for the Cascade UI. Reuses cascade/* — no JS reimplementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cascade.datahub_live import health_check
from cascade.demo import DEFAULT_URN
from cascade.ui_run import load_demo_diff, run_ui_pipeline

_PUBLIC = Path(__file__).resolve().parents[1] / "public"

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
    return {"ok": True, "gms": gms_ok}


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
        # Live GMS / catalog failures surface clearly
        raise HTTPException(status_code=502, detail=str(e)) from e


# SPA fallback when public/ is present (Vercel build copies frontend/dist → public/)
if (_PUBLIC / "index.html").is_file():
    assets = _PUBLIC / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    def spa_index() -> FileResponse:
        return FileResponse(_PUBLIC / "index.html")

    favicon = _PUBLIC / "favicon.svg"
    if favicon.is_file():

        @app.get("/favicon.svg")
        def spa_favicon() -> FileResponse:
            return FileResponse(favicon)
