"""cascade init / doctor — consumer repo bootstrap. Stdlib only."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cascade import __version__
from cascade.config import CascadeConfig, load_config, resolve_rewrite_mode
from cascade.datahub_live import health_check

_TEMPLATES = Path(__file__).resolve().parent / "templates"


def _copy_template(name: str, dest: Path, force: bool) -> str:
    src = _TEMPLATES / name
    if dest.exists() and not force:
        return f"skip {dest} (exists)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text())
    return f"wrote {dest}"


def run_init(root: Path | None = None, *, force: bool = False) -> list[str]:
    root = (root or Path.cwd()).resolve()
    notes = [
        _copy_template("config.json", root / ".cascade" / "config.json", force),
        _copy_template("env.example", root / ".env.example", force),
        _copy_template(
            "github-cascade.yml",
            root / ".github" / "workflows" / "cascade.yml",
            force,
        ),
        "Next: copy .env.example → .env, fill DATAHUB_GMS_URL, map URNs in .cascade/config.json",
        "Add the same DataHub keys as GitHub Actions secrets. Do not commit .env.",
    ]
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        text = gitignore.read_text()
        existing = {ln.strip() for ln in text.splitlines()}
        if ".env" not in existing:
            gitignore.write_text(text.rstrip() + "\n.env\n")
            notes.append("appended .env to .gitignore")
    return notes


def run_doctor(root: Path | None = None) -> tuple[list[str], int]:
    root = (root or Path.cwd()).resolve()
    lines: list[str] = [f"cascade {__version__}"]
    rc = 0

    py = sys.version_info
    if py >= (3, 11):
        lines.append(f"ok   python {py.major}.{py.minor}.{py.micro}")
    else:
        lines.append(f"fail python {py.major}.{py.minor} (need >= 3.11)")
        rc = 1

    cfg_path = root / ".cascade" / "config.json"
    if not cfg_path.is_file():
        lines.append("fail config missing (.cascade/config.json) — run cascade init")
        rc = 1
        cfg = load_config(None)
    else:
        try:
            cfg = load_config(cfg_path)
            lines.append(f"ok   config {cfg_path}")
        except json.JSONDecodeError as e:
            lines.append(f"fail config JSON: {e}")
            rc = 1
            cfg = CascadeConfig()

    if cfg.default_urn or cfg.mappings or os.environ.get("CASCADE_SOURCE_URN"):
        lines.append("ok   URN mapping present")
    else:
        lines.append("fail no default_urn / mappings / CASCADE_SOURCE_URN")
        rc = 1

    gms = os.environ.get("DATAHUB_GMS_URL", "").strip()
    if not gms:
        lines.append("warn DATAHUB_GMS_URL unset (live source will fail)")
    elif health_check(gms):
        lines.append(f"ok   GMS {gms}")
    else:
        lines.append(f"fail GMS unreachable {gms}")
        rc = 1

    mode = resolve_rewrite_mode(config=cfg)
    lines.append(f"ok   rewrite mode {mode}")
    if mode == "llm":
        key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("LLM_MODEL") or cfg.rewrite_model
        if key:
            lines.append("ok   LLM key set")
        else:
            lines.append("fail CASCADE_MODE=llm but no LLM_API_KEY")
            rc = 1
        if model:
            lines.append(f"ok   LLM_MODEL {model}")
        else:
            lines.append("fail CASCADE_MODE=llm requires LLM_MODEL")
            rc = 1

    return lines, rc
